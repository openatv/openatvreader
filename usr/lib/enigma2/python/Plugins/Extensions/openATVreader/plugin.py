#!/usr/bin/env python
# -*- coding: utf-8 -*-

# openATV Forums Reader
# maintainer: lolly - lolly.enigma2@gmail.com

#This plugin for enigma2 settop boxes is free software which entitles you to modify the source code,
#if you clearly identify the original license and developers, but you are not expressly authorized,
#to distribute this software / publish without source code. This applies for the original version,
#but also the version with your changes. That said, you also have the source code of your changes
#distribute / publish to.

##########################################################
########################## FERTIG ########################
##########################################################

from Plugins.Plugin import PluginDescriptor
import openatv
from __init__ import _

def start(session, **kwargs):
	reload(openatv)
	try:
		session.open(openatv.OPENA_TV_HauptScreen)
	except:
		import traceback
		traceback.print_exc()

def Plugins(**kwargs):
	 return PluginDescriptor(name=_("OpenATV Community Reader"), description=_("OpenATV Community Reader"), icon="icon.png", where=[PluginDescriptor.WHERE_EXTENSIONSMENU, PluginDescriptor.WHERE_PLUGINMENU], fnc=start)
