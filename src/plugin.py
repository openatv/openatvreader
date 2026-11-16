#########################################################################################################
#  OpenATVreader, coded by Mr.Servo @ openATV 2024 -2026                                                #
#  -----------------------------------------------------------------------------------------------------#
#  This plugin is licensed under the GNU version 3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>.    #
#  This plugin is NOT free software. It is open source, you are allowed to modify it (if you keep       #
#  the license), but it may not be commercially distributed. Advertise with this tool is not allowed.   #
#  For other uses, permission from the authors is necessary.                                            #
#########################################################################################################
from Plugins.Plugin import PluginDescriptor


def main(session, **kwargs):
	from .ui import openATVMain
	session.open(openATVMain)


PLUGIN_NAME = "OpenATV Reader"
PLUGIN_DESCRIPTION = "Das opena.tv Forum bequem auf dem TV mitlesen"


def menu(menuid, **kwargs):
	return [("OpenATV Reader", main, "openatv_reader", 10)] if menuid == "support" else []


def Plugins(**kwargs):
	PLUGIN_NAME = "OpenATV Reader"
	PLUGIN_DESCRIPTION = "Das opena.tv Forum bequem auf dem TV mitlesen"
	return [PluginDescriptor(name=PLUGIN_NAME,
				description=PLUGIN_DESCRIPTION,
				where=[PluginDescriptor.WHERE_PLUGINMENU],
				icon="plugin.png", fnc=main),
			PluginDescriptor(name=PLUGIN_NAME,
				description=PLUGIN_DESCRIPTION,
				where=[PluginDescriptor.WHERE_EXTENSIONSMENU],
				fnc=main),
			PluginDescriptor(name=PLUGIN_NAME,
				description=PLUGIN_DESCRIPTION,
				where=[PluginDescriptor.WHERE_MENU],
				fnc=menu)
			]
