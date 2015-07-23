# This file is part of MyPaint.
# Copyright (C) 2007-2009 by Martin Renold <martinxyz@gmx.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

"""
This script does all the platform dependent stuff. Its main task is
to figure out where the python modules are.
"""
import sys
import os
import re
import logging
logger = logging.getLogger('mypaint')


class ColorFormatter (logging.Formatter):
    """Minimal ANSI formatter, for use with non-Windows console logging."""

    # ANSI control sequences for various things
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
    FG = 30
    BG = 40
    LEVELCOL = {
        "DEBUG": "\033[%02dm" % (FG+BLUE,),
        "INFO": "\033[%02dm" % (FG+GREEN,),
        "WARNING": "\033[%02dm" % (FG+YELLOW,),
        "ERROR": "\033[%02dm" % (FG+RED,),
        "CRITICAL": "\033[%02d;%02dm" % (FG+RED, BG+BLACK),
    }
    BOLD = "\033[01m"
    BOLDOFF = "\033[22m"
    ITALIC = "\033[03m"
    ITALICOFF = "\033[23m"
    UNDERLINE = "\033[04m"
    UNDERLINEOFF = "\033[24m"
    RESET = "\033[0m"

    # Replace tokens in message format strings to highlight interpolations
    REPLACE_BOLD = lambda m: (ColorFormatter.BOLD +
                              m.group(0) +
                              ColorFormatter.BOLDOFF)
    REPLACE_UNDERLINE = lambda m: (ColorFormatter.UNDERLINE +
                                   m.group(0) +
                                   ColorFormatter.UNDERLINEOFF)
    TOKEN_FORMATTING = [
        (re.compile(r'%r'), REPLACE_BOLD),
        (re.compile(r'%s'), REPLACE_BOLD),
        (re.compile(r'%\+?[0-9.]*d'), REPLACE_BOLD),
        (re.compile(r'%\+?[0-9.]*f'), REPLACE_BOLD),
    ]

    def format(self, record):
        record = logging.makeLogRecord(record.__dict__)
        msg = record.msg
        for token_re, repl in self.TOKEN_FORMATTING:
            msg = token_re.sub(repl, msg)
        record.msg = msg
        record.reset = self.RESET
        record.bold = self.BOLD
        record.boldOff = self.BOLDOFF
        record.italic = self.ITALIC
        record.italicOff = self.ITALICOFF
        record.underline = self.UNDERLINE
        record.underlineOff = self.UNDERLINEOFF
        record.levelCol = ""
        if record.levelname in self.LEVELCOL:
            record.levelCol = self.LEVELCOL[record.levelname]
        return super(ColorFormatter, self).format(record)


def win32_unicode_argv():
    # fix for https://gna.org/bugs/?17739
    # code mostly comes from http://code.activestate.com/recipes/572200/
    """Uses shell32.GetCommandLineArgvW to get sys.argv as a list of Unicode
    strings.

    Versions 2.x of Python don't support Unicode in sys.argv on
    Windows, with the underlying Windows API instead replacing multi-byte
    characters with '?'.
    """
    try:
        from ctypes import POINTER, byref, cdll, c_int, windll
        from ctypes.wintypes import LPCWSTR, LPWSTR

        GetCommandLineW = cdll.kernel32.GetCommandLineW
        GetCommandLineW.argtypes = []
        GetCommandLineW.restype = LPCWSTR
        CommandLineToArgvW = windll.shell32.CommandLineToArgvW
        CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]

        CommandLineToArgvW.restype = POINTER(LPWSTR)
        cmd = GetCommandLineW()
        argc = c_int(0)
        argv = CommandLineToArgvW(cmd, byref(argc))
        if argc.value > 0:
            # Remove Python executable if present
            if argc.value - len(sys.argv) == 1:
                start = 1
            else:
                start = 0
            return [argv[i] for i in xrange(start, argc.value)]
    except:
        logger.exception(
            "Specialized Win32 argument handling failed. Please "
            "help us determine if this code is still needed, "
            "and submit patches if it's not."
        )
        logger.warning("Falling back to POSIX-style argument handling")
        return [s.decode(sys.getfilesystemencoding()) for s in sys.argv]


def get_paths():
    join = os.path.join

    # Convert sys.argv to a list of unicode objects
    # (actually converting sys.argv confuses gtk, thus we add a new variable)
    if sys.platform == 'win32':
        sys.argv_unicode = win32_unicode_argv()
    else:
        sys.argv_unicode = [s.decode(sys.getfilesystemencoding())
                            for s in sys.argv]

    # Script and its location, in canonical absolute form
    scriptfile = os.path.abspath(os.path.normpath(sys.argv_unicode[0]))
    scriptdir = os.path.dirname(scriptfile)
    assert isinstance(scriptfile, unicode)
    assert isinstance(scriptdir, unicode)

    # Determine $prefix
    dir_install = scriptdir
    if os.path.basename(dir_install) == 'bin':
        # This is a normal POSIX-like installation.
        # The Windows standalone distribution works like this too.
        prefix = os.path.dirname(dir_install)
        assert isinstance(prefix, unicode)
        libpath = join(prefix, 'share', 'mypaint')
        libpath_compiled = join(prefix, 'lib', 'mypaint')  # or lib64?
        sys.path.insert(0, libpath)
        sys.path.insert(0, libpath_compiled)
        sys.path.insert(0, join(prefix, 'share'))  # for libmypaint
        localepath = join(prefix, 'share', 'locale')
        localepath_brushlib = localepath
        extradata = join(prefix, 'share')
    elif all(map(os.path.exists, ['brushlib', 'desktop', 'gui', 'lib'])):
        # Testing from within the source tree.
        prefix = None
        libpath = u'.'
        extradata = u'desktop'
        localepath = 'po'
        localepath_brushlib = 'brushlib/po'
    elif sys.platform == 'win32':
        prefix = None
        # this is py2exe point of view, all executables in root of installdir
        # FIXME: not all win32 launches are py2exe; need a better test
        libpath = os.path.realpath(scriptdir)
        sys.path.insert(0, libpath)
        sys.path.insert(0, join(prefix, 'share'))  # for libmypaint
        localepath = join(libpath, 'share', 'locale')
        localepath_brushlib = localepath
        extradata = join(libpath, 'share')
    else:
        raise RuntimeError("Unknown install type; could not determine paths")

    assert isinstance(libpath, unicode)

    try:  # just for a nice error message
        from lib import mypaintlib
    except ImportError:
        logger.exception(
            "Failed to load MyPaint's C extension. "
            "This probably means that MyPaint was not correctly "
            "installed, or was built incorrectly."
        )
        logger.info('script: %r', sys.argv[0])
        logger.info('deduced prefix: %r', prefix)
        logger.info('lib_shared: %r', libpath)
        logger.info('lib_compiled: %r', libpath_compiled)
        logger.info('sys.path: %r', sys.path)
        sys.exit(1)

    datapath = libpath
    if not os.path.isdir(join(datapath, 'brushes')):
        logger.critical('Default brush collection not found!')
        logger.critical('It should have been here: %r', datapath)
        sys.exit(1)

    # Old style config file and user data locations.
    # Return None if using XDG will be correct.
    if sys.platform == 'win32':
        old_confpath = None
    else:
        from lib import helpers
        homepath = helpers.expanduser_unicode(u'~')
        old_confpath = join(homepath, '.mypaint/')

    if old_confpath:
        if not os.path.isdir(old_confpath):
            old_confpath = None
        else:
            logger.info("There is an old-style configuration area in %r",
                        old_confpath)
            logger.info("Its contents can be migrated to $XDG_CONFIG_HOME "
                        "and $XDG_DATA_HOME if you wish.")
            logger.info("See the XDG Base Directory Specification for info.")

    assert isinstance(old_confpath, unicode) or old_confpath is None
    assert isinstance(datapath, unicode)
    assert isinstance(extradata, unicode)

    return datapath, extradata, old_confpath, localepath, localepath_brushlib


def init_gettext(localepath, localepath_brushlib):
    """Intialize locales and gettext.

    This must be done before importing any translated python modules
    (to get global strings translated, especially brushsettings.py).

    """

    import gettext
    import locale
    import lib.i18n

    # Required in Windows for the "Region and Language" settings
    # to take effect.
    lib.i18n.set_i18n_envvars()
    lib.i18n.fixup_i18n_envvars()

    # Internationalization
    # Source of many a problem down the line, so lotsa debugging here.
    logger.debug("localepath: %r", localepath)
    logger.debug("localepath_brushlib: %r", localepath_brushlib)
    logger.debug("getdefaultlocale(): %r", locale.getdefaultlocale())

    # Set the user's preferred locale.
    # https://docs.python.org/2/library/locale.html
    # Required in Windows for the "Region and Language" settings
    # to take effect.
    try:
        setlocale_result = locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        logger.exception("setlocale(LC_ALL, '') failed")
    else:
        logger.debug("setlocale(LC_ALL, ''): %r", setlocale_result)

    # More debugging: show the state after setlocale().
    logger.debug(
        "getpreferredencoding(): %r",
        locale.getpreferredencoding(do_setlocale=False),
    )
    locale_categories = [
        s for s in dir(locale)
        if s.startswith("LC_") and s != "LC_ALL"
    ]
    for category in sorted(locale_categories):
        logger.debug(
            "getlocale(%s): %r",
            category,
            locale.getlocale(getattr(locale, category)),
        )

    # Low-level bindtextdomain with paths.
    # This is still required to hook GtkBuilder up with translated
    # strings; the gettext() way doesn't cut it for external stuff
    # yanked in over GI.
    # https://bugzilla.gnome.org/show_bug.cgi?id=574520#c26
    bindtextdomain = None
    bind_textdomain_codeset = None
    textdomain = None

    # Try the POSIX/Linux way first.
    try:
        bindtextdomain = locale.bindtextdomain
        bind_textdomain_codeset = locale.bind_textdomain_codeset
        textdomain = locale.textdomain
    except AttributeError:
        logger.warning(
            "No bindtextdomain builtins found in module 'locale'."
        )
        logger.info(
            "Trying platform-specific fallback hacks to find "
            "bindtextdomain funcs.",
        )
        # Windows Python binaries tend not to expose bindtextdomain and
        # its buddies anywhere they can be called.
        if sys.platform == 'win32':
            libintl = None
            import ctypes
            for libname in [
                    'libintl-8.dll',  # native for MSYS2'sMINGW32
                    'libintl.dll',  # no known cases, but a potential fallback
                    'intl.dll',  # some old recipes off the internet
                ]:
                try:
                    libintl = ctypes.cdll.LoadLibrary(libname)
                    bindtextdomain = libintl.bindtextdomain
                    bindtextdomain.argtypes = (
                        ctypes.c_char_p,
                        ctypes.c_char_p,
                    )
                    bindtextdomain.restype = ctypes.c_char_p
                    bind_textdomain_codeset = libintl.bind_textdomain_codeset
                    bind_textdomain_codeset.argtypes = (
                        ctypes.c_char_p,
                        ctypes.c_char_p,
                    )
                    bind_textdomain_codeset.restype = ctypes.c_char_p
                    textdomain = libintl.textdomain
                    textdomain.argtypes = (
                        ctypes.c_char_p,
                    )
                    textdomain.restype = ctypes.c_char_p
                except:
                    logger.exception(
                        "Windows: attempt to load bindtextdomain funcs "
                        "from %r failed (ctypes)",
                        libname,
                    )
                else:
                    logger.info(
                        "Windows: found working bindtextdomain funcs "
                        "in %r (ctypes)",
                        libname,
                    )
                    break
        else:
            logger.error(
                "No platform-specific fallback for locating bindtextdomain "
                "is known for %r",
                sys.platform,
            )

    # Bind text domains, i.e. tell libintl+GtkBuilder and Python's where
    # to find message catalogs containing translations.
    textdomains = [
        ("mypaint", localepath),
        ("libmypaint", localepath_brushlib),
    ]
    defaultdom = "mypaint"
    codeset = "UTF-8"
    for dom, path in textdomains:
        # Only call the C library gettext setup funcs if there's a
        # complete set from the same source.
        # Required for translatable strings in GtkBuilder XML
        # to be translated.
        if bindtextdomain and bind_textdomain_codeset and textdomain:
            assert os.path.exists(path)
            assert os.path.isdir(path)
            p = bindtextdomain(dom, path)
            c = bind_textdomain_codeset(dom, codeset)
            logger.debug("C bindtextdomain(%r, %r): %r", dom, path, p)
            logger.debug(
                "C bind_textdomain_codeset(%r, %r): %r",
                dom, codeset, c,
            )
        # Call the implementations in Python's standard gettext module
        # too.  This has proper cross-platform support, but it only
        # initializes the native Python "gettext" module.
        # Required for marked strings in Python source to be translated.
        # See http://docs.python.org/release/2.7/library/locale.html
        p = gettext.bindtextdomain(dom, path)
        c = gettext.bind_textdomain_codeset(dom, codeset)
        logger.debug("Python bindtextdomain(%r, %r): %r", dom, path, p)
        logger.debug(
            "Python bind_textdomain_codeset(%r, %r): %r",
            dom, codeset, c,
        )
    if bindtextdomain and bind_textdomain_codeset and textdomain:
        d = textdomain(defaultdom)
        logger.debug("C textdomain(%r): %r", defaultdom, d)
    d = gettext.textdomain(defaultdom)
    logger.debug("Python textdomain(%r): %r", defaultdom, d)


if __name__ == '__main__':
    # Console logging
    log_format = "%(levelname)s: %(name)s: %(message)s"
    if sys.platform == 'win32':
        # Windows doesn't understand ANSI by default.
        console_handler = logging.StreamHandler(stream=sys.stderr)
        console_formatter = logging.Formatter(log_format)
    else:
        # Assume POSIX.
        # Clone stderr so that later reassignment of sys.stderr won't affect
        # logger if --logfile is used.
        stderr_fd = os.dup(sys.stderr.fileno())
        stderr_fp = os.fdopen(stderr_fd, 'ab', 0)
        # Pretty colors.
        console_handler = logging.StreamHandler(stream=stderr_fp)
        if stderr_fp.isatty():
            log_format = (
                "%(levelCol)s%(levelname)s: "
                "%(bold)s%(name)s%(reset)s%(levelCol)s: "
                "%(message)s%(reset)s")
            console_formatter = ColorFormatter(log_format)
        else:
            console_formatter = logging.Formatter(log_format)
    console_handler.setFormatter(console_formatter)
    logging_level = logging.INFO
    if os.environ.get("MYPAINT_DEBUG", False):
        logging_level = logging.DEBUG
    root_logger = logging.getLogger(None)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging_level)
    if logging_level == logging.DEBUG:
        logger.info("Debugging output enabled via MYPAINT_DEBUG")

    # Path determination
    datapath, extradata, old_confpath, localepath, localepath_brushlib \
        = get_paths()

    # Locale setting
    init_gettext(localepath, localepath_brushlib)

    # Allow an override version string to be burned in during build.  Comes
    # from an active repository's git information and build timestamp, or
    # the release_info file from a tarball release.
    try:
        version = MYPAINT_VERSION_CEREMONIAL
    except NameError:
        version = None

    # Start the app.
    from gui import main
    main.main(datapath, extradata, old_confpath, version=version)
