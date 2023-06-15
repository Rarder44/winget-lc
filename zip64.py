#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple command line utility to create Zip64 files.
For Python 3.3+

Most code are from the standard library `zipfile` and `shutil`.
"""

import os
import sys
import time
import stat
import struct
import zipfile
import logging
import argparse
import threading


class DummyZipFile:

    def __init__(self, *args, **kwargs):
        pass

    def write(self, *args, **kwargs):
        pass

    def close(self):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass

# Provide the tell method for unseekable stream


class _Tellable:

    def __init__(self, fp):
        self.fp = fp
        self.offset = 0

    def write(self, data):
        n = self.fp.write(data)
        self.offset += n
        return n

    def tell(self):
        return self.offset

    def flush(self):
        self.fp.flush()

    def close(self):
        self.fp.close()


class Zip64File(zipfile.ZipFile):

    def __init__(self, file, mode="r", compression=zipfile.ZIP_STORED):
        super().__init__(file, mode, compression, True)
        # Python 3.5- compatible
        try:
            self._fileRefCnt
        except AttributeError:
            self._fileRefCnt = True
        try:
            self._lock
        except AttributeError:
            self._lock = threading.RLock()
        try:
            self._seekable
            self.start_dir
        except AttributeError:
            self._seekable = True
            try:
                self.start_dir = self.fp.tell()
            except (AttributeError, OSError):
                self.fp = _Tellable(self.fp)
                self.start_dir = 0
                self._seekable = False
            else:
                # Some file-like objects can provide tell() but not seek()
                try:
                    self.fp.seek(self.start_dir)
                except (AttributeError, OSError):
                    self._seekable = False

    def write(self, filename, arcname=None, compress_type=None):
        """Put the bytes from filename into the archive under the name
        arcname."""
        if not self.fp:
            raise RuntimeError(
                "Attempt to write to ZIP archive that was already closed")

        st = os.stat(filename)
        isdir = stat.S_ISDIR(st.st_mode)
        mtime = time.localtime(st.st_mtime)
        date_time = mtime[0:6]
        # Create ZipInfo instance to store file information
        if arcname is None:
            arcname = filename
        arcname = os.path.normpath(os.path.splitdrive(arcname)[1])
        while arcname[0] in (os.sep, os.altsep):
            arcname = arcname[1:]
        if isdir:
            arcname += '/'
        zinfo = zipfile.ZipInfo(arcname, date_time)
        zinfo.external_attr = (st[0] & 0xFFFF) << 16      # Unix attributes
        if compress_type is None:
            zinfo.compress_type = self.compression
        else:
            zinfo.compress_type = compress_type

        zinfo.file_size = st.st_size
        zinfo.flag_bits = 0x00
        with self._lock:
            if self._seekable:
                self.fp.seek(self.start_dir)
            zinfo.header_offset = self.fp.tell()    # Start of header bytes
            if zinfo.compress_type == zipfile.ZIP_LZMA:
                # Compressed data includes an end-of-stream (EOS) marker
                zinfo.flag_bits |= 0x02

            self._writecheck(zinfo)
            self._didModify = True

            if isdir:
                zinfo.file_size = 0
                zinfo.compress_size = 0
                zinfo.CRC = 0
                zinfo.external_attr |= 0x10  # MS-DOS directory flag
                self.filelist.append(zinfo)
                self.NameToInfo[zinfo.filename] = zinfo
                self.fp.write(zinfo.FileHeader(False))
                self.start_dir = self.fp.tell()
                return

            cmpr = zipfile._get_compressor(zinfo.compress_type)
            if not self._seekable:
                zinfo.flag_bits |= 0x08
            with open(filename, "rb") as fp:
                # Must overwrite CRC and sizes with correct data later
                zinfo.CRC = CRC = 0
                zinfo.compress_size = compress_size = 0
                # Compressed size can be larger than uncompressed size
                zip64 = True  # Forced
                self.fp.write(zinfo.FileHeader(zip64))
                file_size = 0
                while 1:
                    buf = fp.read(1024 * 8)
                    if not buf:
                        break
                    file_size = file_size + len(buf)
                    CRC = zipfile.crc32(buf, CRC) & 0xffffffff
                    if cmpr:
                        buf = cmpr.compress(buf)
                        compress_size = compress_size + len(buf)
                    self.fp.write(buf)
            if cmpr:
                buf = cmpr.flush()
                compress_size = compress_size + len(buf)
                self.fp.write(buf)
                zinfo.compress_size = compress_size
            else:
                zinfo.compress_size = file_size
            zinfo.CRC = CRC
            zinfo.file_size = file_size
            if zinfo.flag_bits & 0x08:
                # Write CRC and file sizes after the file data
                fmt = '<LQQ' if zip64 else '<LLL'
                self.fp.write(struct.pack(fmt, zinfo.CRC, zinfo.compress_size,
                                          zinfo.file_size))
                self.start_dir = self.fp.tell()
            else:
                if not zip64 and self._allowZip64:
                    if file_size > ZIP64_LIMIT:
                        raise RuntimeError(
                            'File size has increased during compressing')
                    if compress_size > ZIP64_LIMIT:
                        raise RuntimeError(
                            'Compressed size larger than uncompressed size')
                # Seek backwards and write file header (which will now include
                # correct CRC and file sizes)
                self.start_dir = self.fp.tell()  # Preserve current position in file
                self.fp.seek(zinfo.header_offset)
                self.fp.write(zinfo.FileHeader(zip64))
                self.fp.seek(self.start_dir)
            self.filelist.append(zinfo)
            self.NameToInfo[zinfo.filename] = zinfo

    def writestr(self, zinfo_or_arcname, data, compress_type=None):
        """Write a file into the archive.  The contents is 'data', which
        may be either a 'str' or a 'bytes' instance; if it is a 'str',
        it is encoded as UTF-8 first.
        'zinfo_or_arcname' is either a ZipInfo instance or
        the name of the file in the archive."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        if not isinstance(zinfo_or_arcname, ZipInfo):
            zinfo = ZipInfo(filename=zinfo_or_arcname,
                            date_time=time.localtime(time.time())[:6])
            zinfo.compress_type = self.compression
            if zinfo.filename[-1] == '/':
                zinfo.external_attr = 0o40775 << 16   # drwxrwxr-x
                zinfo.external_attr |= 0x10           # MS-DOS directory flag
            else:
                zinfo.external_attr = 0o600 << 16     # ?rw-------
        else:
            zinfo = zinfo_or_arcname

        if not self.fp:
            raise RuntimeError(
                "Attempt to write to ZIP archive that was already closed")

        zinfo.file_size = len(data)            # Uncompressed size
        with self._lock:
            if self._seekable:
                self.fp.seek(self.start_dir)
            zinfo.header_offset = self.fp.tell()    # Start of header data
            if compress_type is not None:
                zinfo.compress_type = compress_type
            zinfo.header_offset = self.fp.tell()    # Start of header data
            if compress_type is not None:
                zinfo.compress_type = compress_type
            if zinfo.compress_type == zipfile.ZIP_LZMA:
                # Compressed data includes an end-of-stream (EOS) marker
                zinfo.flag_bits |= 0x02

            self._writecheck(zinfo)
            self._didModify = True
            zinfo.CRC = crc32(data) & 0xffffffff       # CRC-32 checksum
            co = _get_compressor(zinfo.compress_type)
            if co:
                data = co.compress(data) + co.flush()
                zinfo.compress_size = len(data)    # Compressed size
            else:
                zinfo.compress_size = zinfo.file_size
            zip64 = True  # Forced
            if zip64 and not self._allowZip64:
                raise LargeZipFile("Filesize would require ZIP64 extensions")
            self.fp.write(zinfo.FileHeader(zip64))
            self.fp.write(data)
            if zinfo.flag_bits & 0x08:
                # Write CRC and file sizes after the file data
                fmt = '<LQQ' if zip64 else '<LLL'
                self.fp.write(struct.pack(fmt, zinfo.CRC, zinfo.compress_size,
                                          zinfo.file_size))
            self.fp.flush()
            self.start_dir = self.fp.tell()
            self.filelist.append(zinfo)
            self.NameToInfo[zinfo.filename] = zinfo

    def close(self):
        """Close the file, and for mode 'w', 'x' and 'a' write the ending
        records."""
        if self.fp is None:
            return

        try:
            if self.mode in ('w', 'x', 'a') and self._didModify:  # write ending records
                with self._lock:
                    if self._seekable:
                        self.fp.seek(self.start_dir)
                    self._write_end_record()
        finally:
            fp = self.fp
            self.fp = None
            self._fpclose(fp)

    def _write_end_record(self):
        for zinfo in self.filelist:         # write central directory
            dt = zinfo.date_time
            dosdate = (dt[0] - 1980) << 9 | dt[1] << 5 | dt[2]
            dostime = dt[3] << 11 | dt[4] << 5 | (dt[5] // 2)
            extra = []
            extra.append(zinfo.file_size)
            extra.append(zinfo.compress_size)
            file_size = 0xffffffff
            compress_size = 0xffffffff

            extra.append(zinfo.header_offset)
            header_offset = 0xffffffff

            extra_data = zinfo.extra
            min_version = 0
            if extra:
                # Append a ZIP64 field to the extra's
                extra_data = struct.pack(
                    '<HH' + 'Q' * len(extra),
                    1, 8 * len(extra), *extra) + extra_data

                min_version = zipfile.ZIP64_VERSION

            if zinfo.compress_type == zipfile.ZIP_BZIP2:
                min_version = max(zipfile.BZIP2_VERSION, min_version)
            elif zinfo.compress_type == zipfile.ZIP_LZMA:
                min_version = max(zipfile.LZMA_VERSION, min_version)

            extract_version = max(min_version, zinfo.extract_version)
            create_version = max(min_version, zinfo.create_version)
            try:
                filename, flag_bits = zinfo._encodeFilenameFlags()
                centdir = struct.pack(zipfile.structCentralDir,
                                      zipfile.stringCentralDir, create_version,
                                      zinfo.create_system, extract_version, zinfo.reserved,
                                      flag_bits, zinfo.compress_type, dostime, dosdate,
                                      zinfo.CRC, compress_size, file_size,
                                      len(filename), len(
                                          extra_data), len(zinfo.comment),
                                      0, zinfo.internal_attr, zinfo.external_attr,
                                      header_offset)
            except DeprecationWarning:
                print((structCentralDir, stringCentralDir, create_version,
                       zinfo.create_system, extract_version, zinfo.reserved,
                       zinfo.flag_bits, zinfo.compress_type, dostime, dosdate,
                       zinfo.CRC, compress_size, file_size,
                       len(zinfo.filename), len(
                           extra_data), len(zinfo.comment),
                       0, zinfo.internal_attr, zinfo.external_attr,
                       header_offset), file=sys.stderr)
                raise
            self.fp.write(centdir)
            self.fp.write(filename)
            self.fp.write(extra_data)
            self.fp.write(zinfo.comment)

        pos2 = self.fp.tell()
        # Write end-of-zip-archive record
        centDirCount = len(self.filelist)
        centDirSize = pos2 - self.start_dir
        centDirOffset = self.start_dir
        requires_zip64 = True  # Forced
        if requires_zip64:
            # Need to write the ZIP64 end-of-archive records
            zip64endrec = struct.pack(
                zipfile.structEndArchive64, zipfile.stringEndArchive64,
                44, 45, 45, 0, 0, centDirCount, centDirCount,
                centDirSize, centDirOffset)
            self.fp.write(zip64endrec)

            zip64locrec = struct.pack(
                zipfile.structEndArchive64Locator,
                zipfile.stringEndArchive64Locator, 0, pos2, 1)
            self.fp.write(zip64locrec)
            centDirCount = min(centDirCount, 0xFFFF)
            centDirSize = min(centDirSize, 0xFFFFFFFF)
            centDirOffset = min(centDirOffset, 0xFFFFFFFF)

        endrec = struct.pack(zipfile.structEndArchive, zipfile.stringEndArchive,
                             0, 0, centDirCount, centDirCount,
                             centDirSize, centDirOffset, len(self._comment))
        self.fp.write(endrec)
        self.fp.write(self._comment)
        self.fp.flush()

    def _fpclose(self, fp):
        assert self._fileRefCnt > 0
        self._fileRefCnt -= 1
        if not self._fileRefCnt and not self._filePassed:
            fp.close()


def addToZip(zf, path, zippath, dry_run=0, logger=None):
    if logger is not None:
        logger.info("adding '%s'", path)
    if os.path.isfile(path) and not dry_run:
        zf.write(path, zippath, zipfile.ZIP_DEFLATED)
    elif os.path.isdir(path):
        if zippath and not dry_run:
            zf.write(path, zippath)
        for nm in os.listdir(path):
            addToZip(zf, os.path.join(path, nm), os.path.join(zippath, nm),
                     dry_run, logger)
    # else: ignore


def make_zipfile(zip_filename, filelist, dry_run=0, logger=None, zip64=False):
    """Create a zip file from all the files in 'filelist'.

    The output zip file will be named 'zip_filename'.  Uses the "zipfile" Python
    module. Returns the name of the output zip file.
    """
    if dry_run:
        ZipFile = DummyZipFile
    elif zip64:
        ZipFile = Zip64File
    else:
        ZipFile = zipfile.ZipFile

    with ZipFile(zip_filename, "w") as zf:
        for path in filelist:
            zippath = os.path.basename(path)
            if not zippath:
                zippath = os.path.basename(os.path.dirname(path))
            if zippath in ('', os.curdir, os.pardir):
                zippath = ''
            addToZip(zf, path, zippath, dry_run, logger)

    return zip_filename


def main(argv):
    parser = argparse.ArgumentParser(description="Create Zip64 files.")
    parser.add_argument("-q", "--quiet", action='store_const',
                        default=logging.INFO, const=logging.ERROR, help="log nothing")
    parser.add_argument("-n", "--dry-run", action='store_true',
                        help="show what will be done")
    parser.add_argument("-x", "--no-zip64", action='store_false',
                        default=True, help="don't use Zip64 format if possible")
    parser.add_argument("zipfile", metavar='zipfile.zip',
                        help="paths to archive")
    parser.add_argument("src", nargs='+', help="paths to archive")
    args = parser.parse_args(argv)

    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s', level=args.quiet)

    make_zipfile(args.zipfile, args.src, args.dry_run,
                 logging.getLogger(), args.no_zip64)

if __name__ == '__main__':
    main(sys.argv[1:])
