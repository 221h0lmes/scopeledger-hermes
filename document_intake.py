"""Conservative document intake. Never converts an extraction into a billing claim.

Only user-staged local PDF/DOCX under plugin-owned inbox. All financial
interpretation stays candidate-only until separate source and mapping review.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import io
import json
import os
import secrets
import stat
import tempfile
from pathlib import Path
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from . import storage

NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_. -]{0,120}\.(?:pdf|docx)$", re.I)
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
ROLES = {"agreement", "deliveries", "approvals", "invoices"}
MAX_BYTES = 15 * 1024 * 1024
MAX_PAGES = 120
DIGIT = re.compile(r"(?<![\w])(?:[A-Z]{3}\s*)?\d[\d,]*(?:\.\d{1,2})?(?!\w)")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

class IntakeError(ValueError): pass

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def guard_path_ancestry(data_root: Path, destination: Path):
    """Disallow symlinked plugin-data ancestors and containment escapes.

    Refuse output if any component controlled below data_root is a symlink.
    The actual home path may itself contain ordinary symlinks managed by OS;
    checks start at the dedicated plugin-data directory.
    """
    data_root = Path(data_root)
    destination = Path(destination)
    if data_root.is_symlink():
        raise IntakeError('Unsafe plugin data root symlink')
    try:
        parts = destination.relative_to(data_root).parts
    except ValueError as exc:
        raise IntakeError('Document path escapes plugin data root') from exc
    current = data_root
    for part in parts:
        if part == '..':
            raise IntakeError('Document path escapes plugin data root')
        current = current / part
        if current.is_symlink():
            raise IntakeError('Unsafe symlink in plugin data path: ' + part)


@contextmanager
def secure_output_directory(destination: Path, *, create=True):
    """Pin a directory by walking every component with O_NOFOLLOW."""
    base = storage.data_root()
    destination = Path(destination)
    guard_path_ancestry(base, destination)
    parts = destination.relative_to(base).parts
    if create:
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(base, flags)
    try:
        for component in parts:
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                child = os.open(component, flags, dir_fd=fd)
            except OSError as exc:
                raise IntakeError('Unsafe output ancestor: ' + component) from exc
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def check_output_directory(destination: Path, directory_fd):
    """Refuse to return a pathname that changed identity during publication."""
    with secure_output_directory(destination, create=False) as observed_fd:
        expected, observed = os.fstat(directory_fd), os.fstat(observed_fd)
        if (expected.st_dev, expected.st_ino) != (observed.st_dev, observed.st_ino):
            raise IntakeError('Output directory changed during publication')


def write_immutable_at(directory_fd, leaf: str, value: str):
    """Atomically publish a complete UTF-8 file relative to a pinned directory.

    Caller owns the directory descriptor. No pathnames are reopened for file
    reads, temporary creation, linking or cleanup, including collision paths.
    """
    if not isinstance(leaf, str) or leaf in ('', '.', '..') or Path(leaf).name != leaf:
        raise IntakeError('Output filename must be a basename')
    expected = value.encode('utf-8')
    temporary = None

    def existing_matches():
        try:
            existing = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise IntakeError('Unsafe immutable output') from exc
        with os.fdopen(existing, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode) or stream.read(len(expected) + 1) != expected:
                raise IntakeError('Existing immutable evidence differs; never overwrite')
        return True

    try:
        if existing_matches():
            return
        candidate = '.scopeledger-' + secrets.token_hex(16) + '.tmp'
        created = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=directory_fd)
        temporary = candidate
        with os.fdopen(created, 'wb') as stream:
            stream.write(expected)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, leaf, src_dir_fd=directory_fd, dst_dir_fd=directory_fd, follow_symlinks=False)
        except FileExistsError:
            if not existing_matches():
                raise IntakeError('Concurrent immutable output disappeared')
        os.fsync(directory_fd)
    finally:
        if temporary is not None:
            os.unlink(temporary, dir_fd=directory_fd)


def write_immutable(destination: Path, value: str):
    """Publish evidence once, rejecting symlinked ancestors and leaf paths."""
    destination = Path(destination)
    guard_path_ancestry(storage.data_root(), destination)
    with secure_output_directory(destination.parent) as directory_fd:
        write_immutable_at(directory_fd, destination.name, value)


def _secure_path(slug: str, filename: str) -> Path:
    if not SLUG.fullmatch(slug) or not NAME.fullmatch(filename) or filename.startswith('.'):
        raise IntakeError("Invalid project or document name")
    base = storage.data_root()
    inbox = base / 'inbox'
    guard_path_ancestry(base, inbox / slug)
    if inbox.is_symlink(): raise IntakeError("Unsafe inbox")
    folder = inbox / slug
    if folder.is_symlink(): raise IntakeError("Unsafe project inbox")
    source = folder / filename
    if source.is_symlink() or not source.is_file(): raise IntakeError("Missing or symlinked source")
    if not source.resolve().parent == folder.resolve(): raise IntakeError("Source must be in selected project inbox")
    if not (0 < source.stat().st_size <= MAX_BYTES): raise IntakeError("Document empty or too large")
    return source

def _pdf(data: bytes, path: Path):
    if not data.startswith(b'%PDF-'): raise IntakeError('Not a PDF file')
    # Poppler requires a pathname. Never give it the live original: both
    # subprocesses and the secondary parser must consume the hashed snapshot.
    with tempfile.TemporaryDirectory(prefix='scopeledger-pdf-') as folder:
        snapshot = Path(folder) / 'source.pdf'
        with snapshot.open('xb') as stream:
            stream.write(data)
        snapshot.chmod(0o400)
        return _pdf_snapshot(data, snapshot)


def _pdf_snapshot(data: bytes, path: Path):
    def invoke(args):
        try:
            safe_env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
            safe_env["LANG"] = "C.UTF-8"
            p = subprocess.run(args, capture_output=True, timeout=25, check=True, env=safe_env)
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise IntakeError('Poppler PDF parser unavailable or failed: ' + type(e).__name__) from e
        return p.stdout.decode('utf-8', 'replace')
    info = invoke(['pdfinfo', str(path)])
    m = re.search(r'^Pages:\s*(\d+)$', info, re.M)
    if not m: raise IntakeError('Could not establish PDF page count')
    total = int(m.group(1))
    if not (1 <= total <= MAX_PAGES): raise IntakeError('Unsupported PDF page count')
    pages = []
    issues=[]
    for number in range(1,total+1):
        text = invoke(['pdftotext','-f',str(number),'-l',str(number),'-layout','-enc','UTF-8',str(path),'-'])
        text = text.strip('\f\n\r ')
        if len(text.strip()) < 25: issues.append(f'Page {number}: empty/scanned or too little extractable text')
        pages.append({'page':number, 'text':text, 'numeric_tokens': sorted(DIGIT.findall(text))})
    # Independent parser is required for automated coverage confidence.
    try:
        import fitz
        pdf = fitz.open(stream=data, filetype='pdf')
        if pdf.page_count != total: issues.append('Page count differs between Poppler and PyMuPDF')
        for number, page in enumerate(pdf,1):
            if number>total:break
            other = page.get_text('text')
            if not other.strip() and pages[number-1]['text'].strip():
                issues.append(f'Page {number}: independent parser yielded no text')
            a=set(DIGIT.findall(pages[number-1]['text']))
            b=set(DIGIT.findall(other))
            if a != b:
                issues.append(f'Page {number}: numeric token sets disagree between two parsers')
        pdf.close()
    except ImportError:
        issues.append('Second PDF parser (PyMuPDF) not installed: independent text comparison unavailable')
    except Exception as e:
        issues.append('Second PDF parser failed: ' + type(e).__name__)
    return pages, issues

def _docx(data: bytes, path: Path):
    if not zipfile.is_zipfile(io.BytesIO(data)): raise IntakeError('Not a valid DOCX container')
    issues=[]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        if 'word/document.xml' not in names: raise IntakeError('No main Word document XML')
        if len(names)>2000 or sum(info.file_size for info in z.infolist())>MAX_BYTES*3:
            raise IntakeError('DOCX has unexpectedly large internal parts')
        if any(n.startswith('word/embeddings/') for n in names):
            issues.append('Embedded objects require manual review')
        extra_parts=[n for n in names if re.match(r'word/(?:footnotes|endnotes|comments|header\d*|footer\d*)\.xml$',n)]
        if extra_parts:issues.append('Supplemental DOCX parts require review: '+', '.join(sorted(extra_parts)))
        raw = z.read('word/document.xml')
        root = ET.fromstring(raw)
        # A strict ordered paragraph/table text pass retains table cells and rows.
        body=root.find(W+'body')
        if body is None:raise IntakeError('Missing Word body')
        lines=[]
        def walk_blocks(blocks):
            for child in blocks:
                if child.tag == W+'p':
                    t=''.join(n.text or '' for n in child.iter(W+'t')).strip()
                    if t: lines.append(t)
                elif child.tag == W+'tbl':
                    for row in child.iter(W+'tr'):
                        cells=[' '.join(''.join(n.text or '' for n in p.iter(W+'t')) for p in cell.iter(W+'p')).strip() for cell in row.findall(W+'tc')]
                        lines.append(' | '.join(cells))
                elif child.tag == W+'sdt':
                    issues.append('DOCX content control present: all nested financial text requires visual verification')
                    content = child.find(W+'sdtContent')
                    if content is None:
                        issues.append('DOCX content control has no readable content; manual review required')
                    else:
                        walk_blocks(content)
                elif child.tag not in (W+'sectPr',):
                    # Unknown body blocks may contain content our parser cannot
                    # faithfully display; flag instead of reporting completeness.
                    issues.append('Unsupported DOCX body element: ' + child.tag.split('}')[-1])
        walk_blocks(body)
        if not lines: issues.append('DOCX contains no readable paragraphs/table rows')
        # Resolve tracked edits by expanded XML names; the prefix can be
        # x:, w:, or any other legal alias for the WordprocessingML URI.
        if any(node.tag in {W+'ins',W+'del',W+'moveFrom',W+'moveTo'} for node in root.iter()):
            issues.append('Tracked edits exist; final accepted text is not independently established')
        if any(n.startswith('word/media/') for n in names):
            issues.append('Images are present; embedded text may not have been extracted')
    full='\n'.join(lines)
    try:
        from docx import Document
        d=Document(io.BytesIO(data))
        other='\n'.join(p.text for p in d.paragraphs)
        # No claim of independence of table data; explicitly manual-review tables.
        if not other.strip() and full.strip():issues.append('Secondary DOCX parser found no paragraph text')
    except ImportError:issues.append('Secondary DOCX parser (python-docx) not installed')
    except Exception as e:issues.append('Secondary DOCX parser failed: '+type(e).__name__)
    return [{'page':None,'text':full,'numeric_tokens':sorted(DIGIT.findall(full))}],issues

def inspect(slug: str, filename: str, role: str, *, source_origin='local', drive_file_id=None, drive_revision=None):
    if role not in ROLES: raise IntakeError('Role must be agreement, deliveries, approvals, or invoices')
    if source_origin not in ('local','drive-selected-export'):raise IntakeError('Unrecognized origin')
    if source_origin=='drive-selected-export' and not (isinstance(drive_file_id,str) and 3<=len(drive_file_id)<=200):
        raise IntakeError('Drive-origin record requires a selected file ID')
    source=_secure_path(slug,filename)
    # Record the owner's explicit opt-in outside the inbox so removing the
    # documents cannot silently revert to legacy structured-only auditing.
    from . import intake_gate
    intake_gate.require_document_intake(slug)
    original=source.read_bytes()
    if not (0 < len(original) <= MAX_BYTES): raise IntakeError('Document empty or too large')
    source_hash=_sha(original)
    pages,issues=(_pdf(original,source) if source.suffix.lower()=='.pdf' else _docx(original,source))
    if _sha(source.read_bytes()) != source_hash: raise IntakeError('Source changed during extraction')
    # Do not expose data in filenames; keep snapshots and manifest local only.
    base=storage.data_root()
    root=base/'extractions'/slug/source_hash[:16]
    guard_path_ancestry(base, root)
    if root.is_symlink():raise IntakeError('Extraction directory unsafe')
    basename=source.stem.lower().replace(' ','_')[:45]
    txtpath=root/(basename+'.extracted.txt')
    manifestpath=root/(basename+'.manifest.json')
    text='\n\n'.join(f'[PAGE {p["page"] if p["page"] else "DOCX BODY"}]\n{p["text"]}' for p in pages)
    record={
      'schema_version':'1','original':filename,'source_sha256':source_hash,
      'input_snapshot':'captured-bytes-v1',
      'source_origin':source_origin,'drive_file_id':drive_file_id,'drive_revision':drive_revision,
      'role':role,'project':slug,'page_or_section_count':len(pages),
      'page_coverage':[{'page':p['page'],'characters':len(p['text']), 'numeric_tokens':p['numeric_tokens']} for p in pages],
      'issues':issues, 'extraction_sha256':_sha(text.encode()),
      'extractor':'poppler pdftotext+pdfinfo + pymupdf cross-check' if source.suffix.lower()=='.pdf' else 'python stdlib docx XML + optional python-docx cross-check',
      'review_status':'PENDING_HUMAN_REVIEW', 'financial_mapping_status':'NOT_MAPPED',
      'warning':'Never treat this extraction as a verified or complete invoice ledger without original-page and line-item review.'
    }
    jsontext=json.dumps(record,indent=2,ensure_ascii=False,sort_keys=True)+'\n'
    for target,value in ((txtpath,text),(manifestpath,jsontext)):
        write_immutable(target, value)
    return {'ok':True,'project':slug,'role':role,'source_sha256':source_hash,
            'extracted_path':str(txtpath),'manifest_path':str(manifestpath),
            'page_or_section_count':len(pages),'issues':issues,
            'review_status':'PENDING_HUMAN_REVIEW','financial_mapping_status':'NOT_MAPPED',
            'notice':'This is extraction only; owner-review billable amounts remain unverified until human source/line review and mapping.'}
