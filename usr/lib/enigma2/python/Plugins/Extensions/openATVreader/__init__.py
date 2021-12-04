# -*- coding: utf-8 -*-
import gettext
from os import environ as os_environ

from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_LANGUAGE


def localeInit():
    lang = language.getLanguage()[:2]
    os_environ["LANGUAGE"] = lang
    gettext.bindtextdomain("openATVreader", resolveFilename(SCOPE_PLUGINS, "Extensions/openATVreader/locale"))

def _(txt):
    t = gettext.dgettext("openATVreader", txt)
    if t == txt:
        print "[openATVreader] fallback to default translation for", txt
        t = gettext.gettext(txt)
    return t

localeInit()
language.addCallback(localeInit)
