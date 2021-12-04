#!/usr/bin/env python
# -*- coding: utf-8 -*-

# my_globals.py file from lolly for enigma2 plugins
# maintainer: lolly - lolly.enigma2@gmail.com
#
#This plugin for enigma2 settop boxes is free software which entitles you to modify the source code,
#if you clearly identify the original license and developers, but you are not expressly authorized,
#to distribute this software / publish without source code. This applies for the original version,
#but also the version with your changes. That said, you also have the source code of your changes
#distribute / publish to.

##########################################################
########################## FERTIG ########################
##########################################################

######################
### System Imports ###
######################

from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.ConfigList import ConfigList, ConfigListScreen
from Components.GUIComponent import GUIComponent
from Components.HTMLComponent import HTMLComponent
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmap, MultiContentEntryPixmapAlphaBlend
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Components.Sources.Boolean import Boolean
from Components.config import config, ConfigSubsection, ConfigYesNo, getConfigListEntry, ConfigInteger, ConfigSelection, ConfigText, ConfigPassword, configfile, NoSave
from enigma import eListbox , eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_VALIGN_BOTTOM, loadPNG, getDesktop, ePicLoad, eConsoleAppContainer
from Plugins.Plugin import PluginDescriptor
from os import rename
from Screens.ChannelSelection import ChannelSelection
from Screens.InfoBar import InfoBar
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import SetupSummary
from Screens.Standby import TryQuitMainloop
from Screens.VirtualKeyBoard import VirtualKeyBoard
from skin import loadSkin
from Tools.Directories import fileExists
from Tools.LoadPixmap import LoadPixmap
from twisted.web.client import getPage, error
from urllib import urlencode

import cookielib, md5, re, sys, os, urllib, urllib2, time, shutil, base64

################################
### My Imports and Varaibles ###
################################
import coverhelper
import my_screen
reload(my_screen)
reload(coverhelper)
from coverhelper import *
from my_screen import *

desktopSize = getDesktop(0).size()

pluginPath = '/usr/lib/enigma2/python/Plugins/Extensions/openATVreader'
login_url = 'http://www.opena.tv/login.php?do=login'
check_url = 'http://www.opena.tv/faq.php'
open_url = "http://www.opena.tv/"
git_url = "https://github.com"
build_league_url = 'http://www.opena.tv/vbsoccer.php?do='

if desktopSize.width() == 1920:
	skinsPath = "/skins_fhd/"
else:
	skinsPath = "/skins_hd/"
skinFallback = ""
currentskin = ""
defaultskin = "default"

def cleanHtml(raw_html):
	cleanr =re.compile('<.*?>')
	cleantext = re.sub(cleanr,'', raw_html)
	return cleantext

def cleanLexi(raw_html):
	cleanr =re.compile('<a href="http://lollys-plugins.de/lexikon.*?>')
	cleantext = re.sub(cleanr,'', raw_html)
	return cleantext

def decodeHtml(text):
	text = text.replace('&auml;','ä')
	text = text.replace('&uuml;','ü')
	text = text.replace('&ouml;','ö')
	text = text.replace('&Auml;','Ä')
	text = text.replace('&Uuml;','Ü')
	text = text.replace('&Ouml;','Ö')
	text = text.replace('&szlig;','ß')
	text = text.replace('&bdquo;','"')
	text = text.replace('&ldquo;','"')
	text = text.replace('&hellip;','...')
	text = text.replace('&mdash;','---')
	text = text.replace('&amp;','&')
	text = text.replace('&quot;','\"')
	text = text.replace('&nbsp;','')
	text = text.replace('&raquo;','>>')
	text = text.replace('&rsaquo;','')
	text = text.replace('&#039;','\'')
	text = text.replace('<br />','')
	text = text.replace('</a>','')
	text = text.replace('\t','')
	text = text.replace('<a href="http://www.opena.tv/private.php" rel="nofollow">','')
	text = text.replace('\xe4','ä').replace('\xf6','ö').replace('\xfc','ü').replace('\xdf','ß')
	text = text.replace('\xc4','Ä').replace('\xd6','Ö').replace('\xdc','Ü')
	return text

def applySkinVars(skin,dict):
	for key in dict.keys():
		try:
				skin = skin.replace('{'+key+'}',dict[key])
		except Exception,e:
				print e,"@key=",key
	return skin
