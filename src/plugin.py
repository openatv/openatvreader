#########################################################################################################
#  OpenATVreader, coded by Mr.Servo @ openATV 2024                                                      #
#  -----------------------------------------------------------------------------------------------------#
#  This plugin is licensed under the GNU version 3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>.    #
#  This plugin is NOT free software. It is open source, you are allowed to modify it (if you keep       #
#  the license), but it may not be commercially distributed. Advertise with this tool is not allowed.   #
#  For other uses, permission from the authors is necessary.                                            #
#########################################################################################################
from imghdr import what
from glob import glob
from html import unescape
from os import rename, makedirs, linesep
from os.path import join, exists
from re import search, sub, split, S
from requests import get, exceptions
from shutil import copy2, rmtree
from twisted.internet.reactor import callInThread
from urllib.parse import urlparse, parse_qs

from enigma import getDesktop, eTimer, BT_SCALE, BT_KEEP_ASPECT_RATIO
from Components.ActionMap import ActionMap, NumberActionMap
from Components.ConditionalWidget import BlinkingWidget
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Tools.LoadPixmap import LoadPixmap


class openATVglobals(Screen):
	VERSION = "V2.0b"
	BASEURL = "https://www.opena.tv/"
	AVATARPATH = "/tmp/avatare"
	PLUGINPATH = join(resolveFilename(SCOPE_PLUGINS), "Extensions/OpenATVreader/")
	FAVORITEN = join(PLUGINPATH, "db/favoriten")
	RESOLUTION = "fHD" if getDesktop(0).size().width() > 1300 else "HD"
	POSTSPERMAIN = 5
	POSTSPERTHREAD = 20

	def cleanupDescTags(self, text, singleline=True):  # singleline=True mercilessly cuts the text down to a minimum for MultiContentEntryLines
		if text:  # ATTENTION: The order must not be changed!
			group1, group2 = r'\g<1>', r'\g<2>'
			text = sub(r'\s+', ' ', text) if singleline else sub(r'\n+', '', text).strip()  # remove white spaces or multipe \n
			text = sub(r'<span style="text-align:center;display:block"><img src=".*?" class="postimage" alt="Bild">', '{Bild}' if singleline else '{Bild}\n', text)  # remove embedded pictures
			stext = r'<span style=".*?"><span style="font-size:.*?">(.*?)</div>'
			rtext = search(stext, text)
			if rtext:
				rtext = rtext.group(1).replace("</span>", "").strip()
				rtext = rtext.replace("<br> ", " ") if singleline else rtext.replace("<br> ", "\n")
				rtext = sub(r'<span style="text-decoration:underline"><a href="https:.*?" class="postlink">(.*?)</a>', group1, rtext).strip()
				text = sub(stext, rtext, text)
			text = text.replace("<br>", "") if singleline else text.replace("<br>", "\n")  # necessary for following code
			text = sub(r'<pre class="abbc3_pre"\s*style=".*?"><span style="text-align:center;display:block">(.*?)</pre><span style="text-align:center;display:block">', group1 if singleline else f"{group1}\n", text)  # unwrap pre-formatted
			rtext = f"Datei '{group1}' {group2}" if singleline else f"\nDatei '{group1}'\n{group2}"
			text = sub(r'<div class="inline-attachment">.*?href=".*?">(.*?)</a></dt>\s*<dd>(.*?)</dd>\s*</dl>\s*</div>', rtext, text, flags=S).strip()  # unwrap embedded attachments
			rtext = "{Code}" if singleline else "{Code}\n"
			text = sub(r'<table class="ModTable".*?display:block">(.*?)</span>.*?;display:block">', group1 if singleline else f"{group1}\n", text)  # unwrap moderator message
			text = sub(r'<div class="hidebox hidebox_hidden">.*?"text-align:center;display:block">', '{Versteckt}' if singleline else '{Versteckt}\n', text)  # remove hidden texts
			text = sub(r'<div class="offtopic".*?display:block">(.*?)</span>.*?display:block">', group1 if singleline else f"{group1}\n", text)  # unwrap offtopic texts
			text = sub(r'<div class="abbc3-marquee">.*?display:block">(.*?)</span>.*?display:block">', group1 if singleline else f"{group1}\n", text)  # unwrap running text
			text = sub(r'<div class="spoilwrapper".*?block">.*?</span></div></div>.*?block">', '{Spoiler}' if singleline else '{Spoiler}\n', text)  # remove spoilers
			text = sub(r'<span class="responsive-hide">.*?class="username-coloured">(.*?)</a></strong>.*?</time>', group1, text)  # unwrap userlink
			text = sub(r'<span class="abbc3_strike" style="text-decoration:line-through">(.*?)</span>', group1, text)  # unwrap strikes
			text = sub(r'<pre class="nfo".*?block">(.*?)</span></pre>', group1 if singleline else f"{group1}\n", text)  # unwrap ASCII info
			text = sub(r'<table class="pipe-table">.*?</table>', '{Tabelle}' if singleline else '{Tabelle}\n', text)  # remove tables
			text = sub(r'<div class="codebox">.*?</p><pre><code>(.*?)</code></pre></div>', rtext, text)  # remove codeboxes
			text = sub(r'<ol style="list-style-type:.*?</ol>', '{Auflistung}' if singleline else '{Auflistung}\n', text)  # remove decimal and alpha listings)
			rtext = f"----- {group1} hat geschrieben: -----{{Zitat Anfang}}"
			rtext = "{Zitat}" if singleline else f"{rtext}{'-' * (126 - len(rtext))}\n{group2}\n{'-' * 120}{{Zitat Ende}}-----\n"
			for idx in range(5):  # in case of recursive quotes
				text = sub(r'<blockquote cite=".*?"><div><cite><a href=".*?">(.*?)</a>.*?</cite>(.*?)</div></blockquote>', rtext, text, flags=S)  # unwrap cite blockquotes
			text = sub(r'<span style="text-align:center;display:block"><span style="font-size:.*?">', '', f"{text}</div>", flags=S)  # necessary for some descriptions
			rtext = "{Zitat}" if singleline else f"\n-----{{Zitat Anfang}}{'-' * 126}\n{group1}\n{'-' * 120}{{Zitat Ende}}-----\n"
			text = sub(r'<blockquote class="uncited"><div>(.*?)</div></blockquote>', rtext, text)  # unwrap uncite blockquotes
			text = sub(r'<span style="text-align:center;display:block"><span style="font-size:.*?">', '', f"{text}</div>", flags=S)  # necessary for some descriptions
			rtext = "{Bild}" if singleline else f"\n{{Bild: {group1}}}\n"
			text = sub(r'<div class="inline-attachment">\s*<dl class="file">\s*<dt class="attach-image">.*?</dt>\s*<dd>(.*?)</dd>\s*</dl>\s*</div>', rtext, text, flags=S)  # unwrap pictures
			text = sub(r'<img alt="(.*?)" class="emoji smilies" draggable="false" src=".*?">', '', text)  # unwrap emoicons
			text = sub(r'<span style="text-align:center;display:block">(.*?)/align]', group1, text)  # unwrap centered
			text = sub(r'<ul>.*?</ul>', '{Auflistung}' if singleline else '{Auflistung}\n', text)  # remove free listings
			text = sub(r'<span style="text-align:center;display:block">.*?</span>', "", text)  # remove picture aligns
			text = sub(r'<span style="text-decoration:underline">(.*?)</span>', group1, text)  # unwrap underline
			text = sub(r'<img src=".*?" class="postimage" alt="Bild">', '{Bild}', text)  # remove pictures
			text = sub(r'<span class="dropshadow".*?">(.*?)</span>', group1, text)  # unwrap dropshadows
			text = sub(r'<img class="smilies".*?alt="(.*?)".*?">', group1, text)  # unwrap emoicons
			text = sub(r'<span style="font-family:.*?">(.*?)</span>', group1, text)  # unwrap fonts
			text = sub(r'<span class="fadeEffect">(.*?)</span>', group1, text)  # unwrap fadeEffect
			text = sub(r'<span class="shadow".*?">(.*?)</span>', group1, text)  # unwrap shadows
			text = sub(r'<a href="./viewtopic.php.*?">(.*)</a>', group1, text)  # unwrap topics
			text = sub(r'<span class="glow".*?">(.*?)</span>', group1, text)  # unwrap glows
			text = sub(r'<span class="blur".*?>(.*?)</span>', group1, text)  # unwrap blurs
			text = sub(r'<bdo dir="rtl">(.*?)</bdo>', group1, text)  # unwrap direction change
			text = sub(r'<strong class="text-strong"><span style="color:#.*?">(.*?)</strong>', group1, text)  # unwrap colored bolds
			text = sub(r'<a href=".*?" class="postlink">(.*?)</a>', f"{{Link: {group1}}}", text)  # remove links
			text = sub(r'<span style="color:.*?"><strong class="text-strong">(.*?)<strong class="text-strong">.*?</strong>.*?</strong>', group1, text, flags=S)  # unwrap colored bolds
			text = sub(r'<strong class="text-strong">(.*?)</strong>', group1, text)  # unwrap bolds
			text = sub(r'<span style="color:.*?">(.*?)</span>', group1, text)  # unwrap colors
			text = sub(r'<a href=".*?" class="postlink">(.*?)</a>', f"{{Link: {group1}}}", text)  # remove links
			text = sub(r'<em class="text-italics">(.*?)</em>', group1, text)  # unwrap italic
			text = sub(r'<em class="mention">(.*?)</em>', group1, text)  # unwrap mentionned
			text = sub(r'<div class="notice">.*?</div>', '', text)  # remove notices
			text = sub(r'<sup>(.*?)</sup>', group1, text)  # unwrap superscripts
			text = sub(r'<sub>(.*?)</sub>', group1, text)  # unwrap subscripts
			text = sub(r'<em>.*?</em>', '', text)  # remove change reason
			text = sub(r'<strong>.*?</strong>', '', text)  # change text
			text = text.replace("</span>", "")  # necessary for following code
			text = sub(r'<div style="float:.*?display:block">(.*?)</div><span style="text-align:center;display:block">', group1 if singleline else f"{group1}\n", text)  # unwrap paddings
			text = text.replace("</div>", "\n").replace("</blockquote>", "").strip()  # cleanup remaining scraps
			text = self.cleanupUserTags(text)
			return text if singleline else f"{text}\n"
		return ""

	def cleanupUserTags(self, text):
		if text:
			group1 = r'\g<1>'
			text = sub(r'<b>(.*?)</b>', group1, text)  # remove fat marker
			text = sub(r'<strike>(.*?)</strike>', group1, text)  # remove strikethrough
			text = sub(r'<font\s*color=".*?">(.*?)</font>', group1, text)  # remove font color
			text = sub(r'<marquee\s*direction=".*?" >(.*?)</marquee>', group1, text)  # remove marketing tag
			return text.replace("<b>", "").replace("</b>", "").replace("</font>", "")  # remove breaks / newlines / font tag
		return ""

	def searchOneValue(self, regex, text, fallback, flag_S=False):
		text = search(regex, text, flags=S) if flag_S else search(regex, text)
		return text.group(1) if text else fallback

	def searchTwoValues(self, regex, text, fallback1, fallback2, flag_S=False):
		text = search(regex, text, flags=S) if flag_S else search(regex, text)
		return (text.group(1), text.group(2)) if text else (fallback1, fallback2)

	def downloadPage(self, url, success=None, index=None):
		url = url.encode("ascii", "xmlcharrefreplace").decode().replace(" ", "%20").replace("\n", "")
		try:
			response = get(url.encode("utf-8"))
			response.raise_for_status()
			content = response.content
			if success:
				success(content.decode("utf-8"), index)
			else:
				return content.decode("utf-8")
		except exceptions.RequestException as error:
			self.downloadError(error)

	def showPic(self, pixmap, filename, show=True, scale=True):
		try:  # for openATV 7.x
			if scale:
				pixmap.instance.setPixmapScaleFlags(BT_SCALE | BT_KEEP_ASPECT_RATIO)
			pixmap.instance.setPixmapFromFile(filename)
		except Exception:  # for openATV 6.x
			currPic = LoadPixmap(filename)
			if scale:
				pixmap.instance.setScale(1)
			pixmap.instance.setPixmap(currPic)
		if show:
			pixmap.show()

	def favoriteExists(self, session, favname, favlink):
		self.session = session
		favfound = False
		if favname and favlink and exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN, "r") as f:
					for line in f.read().split("\n"):
						if favlink in line:
							favfound = True
							break
			except OSError as error:
				self.session.open(MessageBox, f"Favoriten konnten nicht geschrieben werden:\n'{error}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
		return favfound

	def writeFavorite(self, session, favname, favlink):
		self.session = session
		if favname and favlink and exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN, "a") as f:
					f.write(f"{favname}\t{favlink}{linesep}")
			except OSError as error:
				self.session.open(MessageBox, f"Favoriten konnten nicht geschrieben werden:\n'{error}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)


class BlinkingLabel(Label, BlinkingWidget):
	def __init__(self, text=''):
		Label.__init__(self, text=text)
		BlinkingWidget.__init__(self)


class getNumber(openATVglobals):
	skin = """
	<screen name="getNumber" position="center,center" size="150,100" backgroundColor="#1A0F0F0F" flags="wfNoBorder" resolution="1280,720" title=" ">
		<widget source="number" render="Label" position="center,center" size="150,100" font="Regular;44" halign="center" valign="center" transparent="1" zPosition="1" />
		<ePixmap position="113,73" size="35,25" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/keypad_HD.png" alphatest="blend" zPosition="1" />
	</screen>"""

	def __init__(self, session, number):
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.field = str(number)
		self["version"] = StaticText(self.VERSION)
		self["headline"] = StaticText()
		self["number"] = StaticText(self.field)
		self['actions'] = NumberActionMap(['SetupActions'], {"ok": self.keyOK,
												 			"cancel": self.quit,
															"1": self.keyNumber,
															"2": self.keyNumber,
															"3": self.keyNumber,
															"4": self.keyNumber,
															"5": self.keyNumber,
															"6": self.keyNumber,
															"7": self.keyNumber,
															"8": self.keyNumber,
															"9": self.keyNumber,
															"0": self.keyNumber})
		self.Timer = eTimer()
		self.Timer.callback.append(self.keyOK)
		self.Timer.start(2000, True)

	def keyNumber(self, number):
		self.Timer.start(2000, True)
		self.field = f"{self.field}{number}"
		self["number"].setText(self.field)
		if len(self.field) >= 4:
			self.keyOK()

	def keyOK(self):
		self.Timer.stop()
		self.close(int(self["number"].getText()))

	def quit(self):
		self.Timer.stop()
		self.close(0)


class openATVFav(openATVglobals):
	skin = """
	<screen name="openATVFav" position="center,center" size="966,546" backgroundColor="#1A0F0F0F" resolution="1280,720" title=" ">
		<ePixmap position="10,10" size="300,50" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/openATV_HD.png" alphatest="blend" zPosition="1" />
		<widget source="version" render="Label" position="290,36" size="43,21" font="Regular;16" halign="left" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="headline" render="Label" position="340,28" size="620,30" font="Regular;24" halign="left" valign="center" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<ePixmap position="13,66" size="940,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<widget source="favmenu" render="Listbox" position="13,73" size="940,420" scrollbarMode="showOnDemand" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1">
			<convert type="TemplatedMultiContent">
				{"template": [
				MultiContentEntryText(pos=(0,0), size=(1200,30), font=0, color="grey" , color_sel="white" , flags=RT_HALIGN_LEFT, text=0)# favorite
				],
				"fonts": [gFont("Regular",22)],
				"itemHeight":30
				}
			</convert>
		</widget>
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_red_HD.png" position="13,500" size="26,38" alphatest="blend" />
		<widget source="key_red" render="Label" position="36,500" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
	</screen>"""

	def __init__(self, session):
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.count = 0
		self.favlist = []
		self["version"] = StaticText(self.VERSION)
		self["headline"] = StaticText("Favoriten")
		self["favmenu"] = List([])
		self["key_red"] = StaticText("Favorit entfernen")
		self["key_yellow"] = StaticText("Favoriten aufrufen")
		self["actions"] = ActionMap(["OkCancelActions",
									"DirectionActions",
									"ColorActions"], {"ok": self.keyOk,
														"cancel": self.close,
														"down": self.keyPageDown,
														"up": self.keyPageUp,
														"red": self.keyRed
														}, -1)
		self.onLayoutFinish.append(self.makeFav)

	def makeFav(self):
		self.count = 0
		menutexts = []
		if exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN, "r") as f:
					for line in f.read().split(linesep):
						if "\t" in line:
							self.count += 1
							favline = line.split("\t")
							favname = favline[0].strip()
							url = favline[1].strip()
							self.favlist.append((favname, url))
							menutexts.append(favname)
			except OSError as error:
				self.session.open(MessageBox, f"Favoriten konnten nicht gelesen werden:\n'{error}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			if not self.count:
				title = "{keine Einträge vorhanden}"
				self.favlist.append((title, "", ""))
				menutexts.append((title))
			self["favmenu"].updateList(menutexts)

	def keyOk(self):
		curridx = self["favmenu"].getCurrentIndex()
		if self.favlist:
			favlink = self.favlist[curridx][1]
			if favlink:
					self.session.open(openATVMain, favlink=favlink, favmenu=True)

	def keyRed(self):
		if exists(self.FAVORITEN):
			curridx = self["favmenu"].getCurrentIndex()
			favname = self.favlist[curridx][0]
			favlink = self.favlist[curridx][1]
			if favname and favlink:
				self.session.openWithCallback(boundFunction(self.red_return, favname, favlink), MessageBox, f"'{favname}'\n\naus den Favoriten entfernen?\n", MessageBox.TYPE_YESNO, timeout=30, default=False)

	def red_return(self, favname, favlink, answer):
		if answer is True:
			data = ""
			try:
				with open(self.FAVORITEN, "r") as f:
					for line in f.read().split("\n"):
						if favlink not in line and line != "\n":
							data += f"{line}{linesep}"
			except OSError as error:
				self.session.open(MessageBox, f"Favoriten konnten nicht gelesen werden:\n'{error}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			try:
				with open(f"{self.FAVORITEN}.new", "w") as f:
					f.write(data)
				rename(f"{self.FAVORITEN}.new", self.FAVORITEN)
			except OSError as error:
				self.session.open(MessageBox, f"Favoriten konnten nicht gelesen werden:\n'{error}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			self.favlist = []
			self.makeFav()

	def keyPageDown(self):
		self["favmenu"].down()

	def keyPageUp(self):
		self["favmenu"].up()


class openATVPost(openATVglobals):
	skin = """
	<screen name="openATVPost" position="center,center" size="1233,680" backgroundColor="#1A0F0F0F" resolution="1280,720" title=" ">
		<ePixmap position="10,10" size="300,50" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/openATV_HD.png" alphatest="blend" zPosition="1" />
		<widget source="version" render="Label" position="290,36" size="43,21" font="Regular;16" halign="left" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="headline" render="Label" position="340,28" size="750,30" font="Regular;24" halign="left" valign="center" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="postid" render="Label" position="1100,6" size="100,21" font="Regular;16" halign="right" valign="center" foregroundColor="grey" transparent="1" zPosition="1" />
		<widget source="postnr" render="Label" position="1100,26" size="100,30" font="Regular;24" halign="right" valign="center" foregroundColor="grey" transparent="1" zPosition="1" />
		<ePixmap position="13,66" size="1200,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<widget name="avatar" position="21,72" size="69,69" alphatest="blend" transparent="1" zPosition="1" />
		<widget name="online" position="24,144" size="64,16" alphatest="blend" transparent="1" zPosition="1" />
		<widget source="username" render="Label" position="113,76" size="266,30" font="Regular;24" halign="center" valign="center" transparent="1" zPosition="1" foregroundColor="#0092cbdf" />
		<widget source="usertitle" render="Label" position="113,133" size="266,28" font="Regular;21" halign="center" valign="center" foregroundColor="grey" transparent="1" zPosition="1" />
		<widget name="userrank" position="173,106" size="150,26" alphatest="blend" transparent="1" zPosition="1" />
		<widget source="postcnt" render="Label" position="426,80" size="200,28" font="Regular;21" halign="left" valign="center" foregroundColor="#0092cbdf" transparent="1" zPosition="1" />
		<widget source="thxgiven" render="Label" position="426,106" size="266,28" font="Regular;21" halign="left" valign="center" foregroundColor="#00b2b300" transparent="1" zPosition="1" />
		<widget source="thxreceived" render="Label" position="426,133" size="266,28" font="Regular;21" halign="left" valign="center" foregroundColor="#005fb300" transparent="1" zPosition="1" />
		<widget source="residence" render="Label" position="866,80" size="333,28" font="Regular;21" halign="right" valign="center" foregroundColor="#0092cbdf" transparent="1" zPosition="1" />
		<widget source="registered" render="Label" position="866,106" size="333,28" font="Regular;21" halign="right" valign="center" foregroundColor="#00b2b300" transparent="1" zPosition="1" />
		<widget source="datum" render="Label" position="866,133" size="333,28" font="Regular;21" halign="right" valign="center" foregroundColor="#005fb300" transparent="1" zPosition="1" />
		<ePixmap position="13,166" size="1200,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<widget name="textpage" position="26,186" size="1173,433" font="Regular;24" halign="left" foregroundColor="white" scrollbarMode="showOnDemand" transparent="1" zPosition="1" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_red_HD.png" position="13,636" size="26,38" alphatest="blend" />
		<widget source="key_red" render="Label" position="36,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
	</screen>"""

	def __init__(self, session, postdetails, favmenu):
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.postdetails = postdetails
		self.favmenu = favmenu
		self.posttitle = ""
		self.postid = ""
		self.postnr = ""
		self["version"] = StaticText(self.VERSION)
		self["headline"] = StaticText()
		self["postid"] = StaticText()
		self["postnr"] = StaticText()
		self["online"] = Pixmap()
		self["avatar"] = Pixmap()
		self["username"] = StaticText()
		self["usertitle"] = StaticText()
		self["userrank"] = Pixmap()
		self["postcnt"] = StaticText()
		self["thxgiven"] = StaticText()
		self["thxreceived"] = StaticText()
		self["registered"] = StaticText()
		self["residence"] = StaticText()
		self["datum"] = StaticText()
		self["textpage"] = ScrollLabel()
		self["key_red"] = StaticText("Favorit hinzufügen")
		self["key_yellow"] = StaticText("Favoriten aufrufen")
		self["NumberActions"] = ActionMap(["NumberActions",
												"OkCancelActions",
												"DirectionActions",
												"ChannelSelectBaseActions",
												"MovieSelectionActions",
												"ColorActions"], {"cancel": self.keyExit,
																	"down": self.keyDown,
																	"up": self.keyUp,
																	"right": self.keyPageDown,
																	"left": self.keyPageUp,
																	"nextBouquet": self.keyPageDown,
																	"prevBouquet": self.keyPageUp,
																	"yellow": self.keyYellow,
																	"red": self.keyRed
																	}, -1)
		self.onLayoutFinish.append(self.makePost)

	def makePost(self):
		posttitle, postid, postnr, avatarlink, online, username, usertitle, userrank, residence, postcnt, thxgiven, thxreceived, registered, date, fulldesc = self.postdetails
		self.posttitle = posttitle
		self.postid = postid
		self.postnr = postnr
		desc = self.cleanupDescTags(fulldesc, singleline=False)
		self.handleIcon(self["avatar"], avatarlink)
		if userrank:
			self.handleIcon(self["userrank"], userrank)
		self.showPic(self["online"], join(self.PLUGINPATH, f"{'icons/online' if online else 'icons/offline'}_{self.RESOLUTION}.png"), scale=False)
		self["headline"].setText(posttitle)
		self["postid"].setText(f"ID: {postid}")
		self["postnr"].setText(postnr)
		self["username"].setText(username)
		self["usertitle"].setText(usertitle)
		self["postcnt"].setText(f"{postcnt} Beiträge")
		self["thxgiven"].setText(f"{thxgiven} Thanks gegeben")
		self["thxreceived"].setText(f"{thxreceived} Thanks bekommen")
		self["residence"].setText(f"Wohnort:{residence}")
		self["registered"].setText(f"Registriert seit {registered}")
		self["datum"].setText(f"Beitrag von {date} Uhr")
		self["textpage"].setText(desc)

	def handleIcon(self, widget, url):
		if widget:
			filename = join(self.AVATARPATH, f"{url[url.rfind('?avatar=') + 8:].split('.')[0]}.*") if url else join(self.PLUGINPATH, "icons/unknown.png")
			picfiles = glob(filename)  # possibly the file name had to be renamed according to the correct image type
			if picfiles and exists(picfiles[0]):  # use first hit found
				self.showPic(widget, picfiles[0])
			else:
				callInThread(self.iconDL, widget, url)

	def iconDL(self, widget, url):
		url = url.encode("ascii", "xmlcharrefreplace").decode().replace(" ", "%20").replace("\n", "")
		filename = join(self.AVATARPATH, url[url.rfind("/") + 1:])
		try:
			response = get(url.encode("utf-8"))
			response.raise_for_status()
			content = response.content
			response.close()
			with open(filename, "wb") as f:
				f.write(content)
			fileparts = filename.split(".")
			pictype = what(filename)
			if pictype and pictype != fileparts[1]:  # Some avatars were incorrectly listed as .GIF although they are .JPG or .PNG
				newfname = f"{fileparts[0]}.{pictype.replace("jpeg", "jpg")}"
				rename(filename, newfname)
				filename = newfname
			self.showPic(widget, filename)
		except exceptions.RequestException as error:
			self.downloadError(error)

	def downloadError(self, error):
		self.session.open(MessageBox, f"Der opena.tv Server ist zur Zeit nicht erreichbar.\n{error}", MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)

	def keyYellow(self):
		if self.favmenu:
			self.session.open(MessageBox, "Dieses Fenster wurde bereits als Favorit geöffnet!\nUm auf die Favoritenliste zurückzukommen, bitte '2x Verlassen/Exit' drücken!\n", type=MessageBox.TYPE_INFO, timeout=5, close_on_any_key=True)
		else:
			self.session.open(openATVFav)

	def keyRed(self):
		favname = f"POST #{self.postnr} von '{self.posttitle}'"
		favlink = f"{self.BASEURL}/viewtopic.php?p={self.postid}#p{self.postid}"  # postlink, e.g. https://www.opena.tv/viewtopic.php?p=570564#p570564
		if self.favoriteExists(self.session, favname, favlink):
			self.session.open(MessageBox, f"ABBRUCH!\n\n'{favname}'\n\nist bereits in den Favoriten vorhanden.\n", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
		else:
			self.session.openWithCallback(boundFunction(self.red_return, favname, favlink), MessageBox, f"'{favname}'\n\nzu den Favoriten hinzufügen?\n", MessageBox.TYPE_YESNO, timeout=30)

	def red_return(self, favname, favlink, answer):
		if answer is True:
			self.writeFavorite(self.session, favname, favlink)

	def keyDown(self):
		self["textpage"].pageDown()

	def keyUp(self):
		self["textpage"].pageUp()

	def keyPageDown(self):
		self["textpage"].pageDown()

	def keyPageUp(self):
		self["textpage"].pageUp()

	def keyExit(self):
		self.close()


class openATVMain(openATVglobals):
	skin = """
	<screen name="openATVMain" position="center,center" size="1233,680" backgroundColor="#1A0F0F0F" resolution="1280,720" title=" ">
		<ePixmap position="10,10" size="300,50" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/openATV_HD.png" alphatest="blend" zPosition="1" />
		<widget source="version" render="Label" position="290,36" size="43,21" font="Regular;16" halign="left" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="headline" render="Label" position="340,29" size="640,30" font="Regular;24" halign="left" valign="bottom" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget name="waiting" position="340,29" size="750,30" font="Regular;20" halign="left" valign="bottom" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="global.CurrentTime" render="Label" position="1080,10" size="130,28" font="Regular;28" noWrap="1" halign="right" valign="top" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Default</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="980,10" size="120,26" font="Regular;20" noWrap="1" halign="right" valign="bottom" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Format:%A</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="980,34" size="120,26" font="Regular;20" noWrap="1" halign="right" valign="bottom" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Format:%e. %B</convert>
		</widget>
		<widget source="pagecount" render="Label" position="1080,36" size="130,26" font="Regular;16" halign="right" valign="center" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="menu" render="Listbox" position="13,66" size="1200,560" scrollbarMode="showOnDemand" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1">
			<convert type="TemplatedMultiContent">
				{"templates":
					{"default": (80,[ # index
						MultiContentEntryPixmapAlphaTest(pos=(0,0), size=(1200,1), png=6), # line separator
						MultiContentEntryText(pos=(6,2), size=(960,34), font=0, color="grey", color_sel="white", flags=RT_HALIGN_LEFT|RT_ELLIPSIS, text=0),  # theme
						MultiContentEntryText(pos=(6,28), size=(960,32), font=1, color=0x003ca2c6, color_sel=0x00a6a6a6, flags=RT_HALIGN_LEFT|RT_WRAP|RT_ELLIPSIS, text=1),  # forum
						MultiContentEntryText(pos=(6,52), size=(960,32), font=1, color=0x003ca2c6, color_sel=0x00a6a6a6, flags=RT_HALIGN_LEFT|RT_WRAP|RT_ELLIPSIS, text=2),  # description
						MultiContentEntryText(pos=(940,2), size=(232,30), font=2, color=0x005fb300, color_sel=0x0088ff00, flags=RT_HALIGN_RIGHT, text=3),  # date
						MultiContentEntryText(pos=(940,24), size=(232,34), font=0, color=0x00b2b300, color_sel=0x00ffff00, flags=RT_HALIGN_RIGHT, text=4),  # user
						MultiContentEntryText(pos=(940,54), size=(232,30), font=2, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_RIGHT, text=5)  # statistic
						]),
						"thread": (93,[
						MultiContentEntryPixmapAlphaTest(pos=(0,0), size=(1200,1), png=4), # line separator
						MultiContentEntryPixmapAlphaBlend(pos=(6,2), size=(70,70), flags=BT_HALIGN_LEFT|BT_VALIGN_CENTER|BT_SCALE|BT_KEEP_ASPECT_RATIO, png=5),  # avatar
						MultiContentEntryPixmapAlphaBlend(pos=(9,72), size=(64,16), png=6),  # online
						MultiContentEntryText(pos=(106,6), size=(860,76), font=1, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_LEFT|RT_WRAP, text=0), # description
						MultiContentEntryText(pos=(940,6), size=(232,30), font=2, color=0x005fb300, color_sel=0x0088ff00, flags=RT_HALIGN_RIGHT, text=1),  # date
						MultiContentEntryText(pos=(940,30), size=(232,34), font=0, color=0x00b2b300, color_sel=0x00ffff00, flags=RT_HALIGN_RIGHT, text=2),  # user
						MultiContentEntryText(pos=(940,60), size=(232,30), font=2, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_RIGHT, text=3)  # postcount
						])
					},
				"fonts": [gFont("Regular",22), gFont("Regular",20), gFont("Regular",18)]
				}
			</convert>
		</widget>
		<ePixmap position="13,630" size="1200,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_red_HD.png" position="13,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_green_HD.png" position="223,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_yellow_HD.png" position="433,636" size="26,38" alphatest="blend" />
		<widget source="key_red" render="Label" position="36,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_green" render="Label" position="246,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_yellow" render="Label" position="456,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget name="button_page" position="823,646" size="43,20" alphatest="blend" zPosition="1" />
		<widget source="key_page" render="Label" position="873,636" size="200,38" font="Regular;18" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" halign="left" valign="center" />
		<widget name="button_keypad" position="1026,643" size="35,25" alphatest="blend" zPosition="1" />
		<widget source="key_keypad" render="Label" position="1066,636" size="200,38" font="Regular;18" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" halign="left" valign="center" />
	</screen>"""

	def __init__(self, session, favlink="", favmenu=False):
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.favlink = favlink
		self.threadlink = ""
		self.currmode = "menu"
		self.ready = False
		self.favmenu = favmenu
		self.currpage = 1
		self.maxpages = 1
		self.oldthreadlink = ""
		self.oldmenuindex = 0
		self.postlist = []
		self.threadlinks = []
		self.maintexts = []
		self.threadtexts = []
		self.menupics = []
		self.threadpics = []
		self.avatarDLlist = []
		self["version"] = StaticText(self.VERSION)
		self["headline"] = StaticText()
		self["waiting"] = BlinkingLabel("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		self["button_yellow"] = Label()
		self["button_page"] = Pixmap()
		self["button_page"].hide()
		self["button_keypad"] = Pixmap()
		self["button_keypad"].hide()
		self["key_red"] = StaticText("Favorit hinzufügen")
		self["key_green"] = StaticText("Alles aktualisieren")
		self["key_yellow"] = StaticText()
		self["pagecount"] = StaticText()
		self["key_page"] = StaticText()
		self["key_keypad"] = StaticText()
		self["menu"] = List([])
		self["NumberActions"] = NumberActionMap(["NumberActions",
												"WizardActions",
												"NumberActions",
												"DirectionActions",
												"MenuActions",
												"ChannelSelectBaseActions",
												"ColorActions"], {"ok": self.keyOk,
			   														"back": self.keyExit,
																	"cancel": self.keyExit,
																	"red": self.keyRed,
																	"green": self.keyGreen,
																	"yellow": self.keyYellow,
																	"up": self.keyUp,
																	"down": self.keyDown,
																	"right": self.keyPageDown,
																	"left": self.keyPageUp,
																	"nextBouquet": self.prevPage,
																	"prevBouquet": self.nextPage,
																	 "0": self.gotoPage,
																	 "1": self.gotoPage,
																	 "2": self.gotoPage,
																	 "3": self.gotoPage,
																	 "4": self.gotoPage,
																	 "5": self.gotoPage,
																	 "6": self.gotoPage,
																	 "7": self.gotoPage,
																	 "8": self.gotoPage,
																	 "9": self.gotoPage
																 }, -1)
		self.checkFiles()
		linefile = join(self.PLUGINPATH, f"icons/line_{self.RESOLUTION}.png")
		self.linepix = LoadPixmap(cached=True, path=linefile) if exists(linefile) else None
		statusfile = join(self.PLUGINPATH, f"icons/online_{self.RESOLUTION}.png")
		self.online = LoadPixmap(cached=True, path=statusfile) if exists(statusfile) else None
		statusfile = join(self.PLUGINPATH, f"icons/offline_{self.RESOLUTION}.png")
		self.offline = LoadPixmap(cached=True, path=statusfile) if exists(statusfile) else None
		copy2(join(self.PLUGINPATH, "icons/user_stat.png"), self.AVATARPATH)
		copy2(join(self.PLUGINPATH, "icons/unknown.png"), self.AVATARPATH)
		self.onLayoutFinish.append(self.onLayoutFinished)

	def onLayoutFinished(self):
		self.showPic(self["button_page"], join(self.PLUGINPATH, f"icons/key_updown_{self.RESOLUTION}.png"), show=False, scale=False)
		self.showPic(self["button_keypad"], join(self.PLUGINPATH, f"icons/keypad_{self.RESOLUTION}.png"), show=False, scale=False)
		if self.favmenu:
			self["button_yellow"].hide()
			self["key_yellow"].setText("")
		else:
			self["button_yellow"].show()
			self["key_yellow"].setText("Favoriten aufrufen")
		if self.favlink or self.threadlink:
			callInThread(self.makeThread)
		else:
			callInThread(self.makeMenu)

	def makeMenu(self, index=None):
		self["menu"].style = "default"
		self["menu"].updateList([])
		self["waiting"].setText("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		self["headline"].setText("")
		self["pagecount"].setText("")
		self.currmode = "menu"
		self.oldmenuindex = 0
		self.menupics = []
		self.maintexts = []
		self.threadlink = ""
		self.threadlinks = []
		self.ready = False
		userlist = []
		for postcount in range(0, 5 * self.POSTSPERMAIN, self.POSTSPERMAIN):  # get first 5 pages
			output = self.downloadPage(f"{self.BASEURL}index.php?recent_topics_start={postcount}")
			if output:
				startpos = output.find('<ul class="topiclist topics collapsible">')
				endpos = output.find('">openATV Board</a></div></dt>')
				cutout = unescape(output[startpos:endpos])
				for post in split(r'<li class="row bg', cutout, flags=S)[1:]:
					username = self.cleanupUserTags(self.searchOneValue(r'class="usernam.*?">(.*?)</', post, ""))
					userlist.append(username)
					avatar, online = None, False  # not available on starting page
					title = self.searchOneValue(r'class="topictitle">(.*?)</a>', post, "{kein Thema}")
					forum = self.searchOneValue(r'» in <a href=".*?">(.*?)</a> » <a href="', post, "{neues Forum}")
					forum = f"Forum: {forum}"
					creator, created = self.searchTwoValues(r'class="username">(.*?)</a>.*?">(.*?)</a>', post, "", "", flag_S=True)
					desc = f"von '{creator}' am {created}" if creator and created else "neues Thema erstellt"
					date = self.searchOneValue(r'title="Gehe zum letzten Beitrag">(.*?)</a>', post, "{kein Datum}")
					stats = []
					accesses = self.searchOneValue(r'<dd class="views">(.*?)<dfn>Zugriffe</dfn></dd>', post, "0").strip()
					accesses = int(accesses) if accesses.isdigit() else 0
					if accesses:
						stats.append(f"{accesses} Zugriffe")
					answers = self.searchOneValue(r'<dd class="posts">(.*?)<dfn>Antworten</dfn></dd>', post, "0").strip()
					answers = int(answers) if answers.isdigit() else 0
					if answers:
						stats.append(f"{answers} Antwort(en)")
					stats = ", ".join(stats)
					url = self.searchOneValue(r'<div class="list-inner">\s*<a href="./(.*?)" class="', post, "")  # e.g. viewtopic.php?t=66622&sid=a6b61343ae1c45fcd16fb8a172e1fd7f
					threadid = parse_qs(urlparse(url).query)['t'][0]
					self.threadlinks.append(f"{self.BASEURL}viewtopic.php?t={threadid}&start={answers // self.POSTSPERTHREAD * self.POSTSPERTHREAD}" if threadid else "")
					self.maintexts.append([title, forum, desc, date, username, stats])
					self.menupics.append([avatar, online])
		userlist = list(dict.fromkeys(userlist))  # remove dupes
		userlist = ", ".join(userlist)
		userlist = f"{userlist[:200]}…" if len(userlist) > 200 or userlist.endswith(",") else userlist
		self.threadlinks.append("")
		self.maintexts.append(["beteiligte Benutzer", userlist, "", "", "", ""])
		self.menupics.append(["./icons/user_stat.png", False])
		self["waiting"].stopBlinking()
		self["headline"].setText("aktuelle Themen")
		self.ready = True
		self.updateSkin()
		if index:
			self["menu"].setCurrentIndex(index)

	def makeThread(self, movetoend=False):
		self.currmode = "thread"
		self["menu"].style = "thread"
		self["menu"].updateList([])
		self["waiting"].setText("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		self["headline"].setText("")
		self.ready = False
		userlist = []
		self.postlist = []
		self.threadpics = []
		self.threadtexts = []
		output = self.downloadPage(self.favlink if self.favlink else self.threadlink)
		if output:
			endpos = output.find('<div class="action-bar actions-jump">')
			cutout = unescape(output[:endpos])
			pagination = self.searchOneValue(r'<div class="pagination">(.*?)</div>', cutout, "", flag_S=True)
			currpage, maxpages = self.searchTwoValues(r'Seite <strong>(.*?)</strong> von <strong>(.*?)</strong>', pagination, "1", "1", flag_S=True)
			self.currpage, self.maxpages = int(currpage), int(maxpages)
			posttitle = self.searchOneValue(r'<title>(.*?)</title>', cutout, "{kein Titel gefunden}").split(" - openATV Forum")[0]
			posttitle = posttitle[:posttitle.find(" - Seite")]
			self["waiting"].stopBlinking()
			self["headline"].setText(f"THEMA: {posttitle}")
			self["pagecount"].setText(f"Seite {currpage} von {maxpages}")
			for post in split(r'<dl class="postprofile"', cutout, flags=S)[1:]:
				postid = self.searchOneValue(r'id="profile(.*?)"', post, "{n/v}")
				postnr = self.searchOneValue(r'return false;">(.*?)</a></span>', post, "")
				online = self.searchOneValue(r'<div id=".*?" class="post has-profile bg.*? (.*?)">', post, "") == True
				avatarlink = self.searchOneValue(r'<img class="avatar" src="./(.*?)"', post, "")
				avatarlink = f"{self.BASEURL}{avatarlink}" if avatarlink else None
				self.handleAvatar(avatarlink)  # trigger download of Avatar
				username = self.cleanupUserTags(self.searchOneValue(r'class="usernam.*?">(.*?)</', post, ""))
				if "gelöschter benutzer" in username.lower():
					username = "{gelöscht}"
				usertitle, userrank = self.searchTwoValues(r'<dd class="profile-rank">(.*?)<br /><img src="./(.*?)"', post, "{gelöscht}", None)
				userrank = f"{self.BASEURL}{userrank}"
				residence = self.searchOneValue(r'<strong>Wohnort:</strong>(.*?)</dd>', post, ' {kein Wohnort benannt}')
				postcnt = "%s Beiträge" % self.searchOneValue(r'Beiträge:</strong> <a href=".*?">(.*?)</a>', post, "0")
				thxgiven = self.searchOneValue(r'/true.*?">(.*?)</a></dd>', post, "keine")
				thxreceived = self.searchOneValue(r'/false.*?">(.*?)</a></dd>', post, "keine")
				registered = self.searchOneValue(r'<strong>Registriert:</strong>(.*?)</dd>', post, "{unbekannt}").replace("  ", " ")
				date = self.searchOneValue(r'<time datetime=".*?">(.*?)</time>', post, "{kein Datum/Uhrzeit}")
				signature = self.searchOneValue(r'<div id=".*?" class="signature">(.*?)\s*</div>', post, "", flag_S=True)
				fulldesc = self.searchOneValue(r'<div class="content">(.*?)\s*<div id=', post, "{keine Beschreibung}", flag_S=True)
				cngreason = self.searchOneValue(r'<em>(.*?)</em>', post, "kein Änderungsgrund angegeben")
				cnguser, cngdate = self.searchTwoValues(r'<div class="notice">\s*Zuletzt geändert von <a href=".*?">(.*?)</a>(.*?)</div>', post, "", "", flag_S=True)
				changes = f"Zuletzt geändert von {cnguser.strip()} {cngdate.replace("<br />", "").strip()}<br>Grund: {cngreason.strip()}" if cnguser and cngdate else ""
				fulldesc += f"{signature} {changes}"
				desc = self.cleanupDescTags(f"{fulldesc}\n")
				desc = f"{postnr}: {desc[:270]}{desc[270:desc.find(' ', 270)]}…" if len(desc) > 270 else f"{postnr}: {desc}"
				self.threadtexts.append([desc, date, username, postcnt])
				self.threadpics.append([avatarlink, online])
				self.postlist.append((posttitle, postid, postnr, avatarlink, online, username, usertitle, userrank, residence, postcnt, thxgiven, thxreceived, registered, date, fulldesc))
				userlist.append((username))
			userlist = list(dict.fromkeys(userlist))  # remove dupes
			userlist = ", ".join(userlist)
			userlist = f"beteiligte Benutzer\n{userlist[:200]}…" if len(userlist) > 200 or userlist.endswith(",") else f"beteiligte Benutzer\n{userlist}"
			self.threadtexts.append([userlist, "", "", ""])
			self.threadpics.append(["./icons/user_stat.png", False])
			self.ready = True
			self.updateSkin()
			if movetoend:
				self["menu"].goBottom()
				self["menu"].goLineUp()

	def updateSkin(self):
		skinpix = []
		for menupic in self.menupics if self.currmode == "menu" else self.threadpics:
			if self.currmode == "thread":
				avatarpix = self.handleAvatar(menupic[0])
				statuspix = self.online if menupic[1] else self.offline
			else:
				avatarpix = None
				statuspix = None
			skinpix.append([self.linepix, avatarpix, statuspix])
		skinlist = []
		for idx, menulist in enumerate(self.maintexts if self.currmode == "menu" else self.threadtexts):
			skinlist.append(tuple(menulist + skinpix[idx]))
		self["menu"].updateList(skinlist)
		if self.currmode == "thread" and self.maxpages > 1:
			self["button_page"].show()
			self["button_keypad"].show()
			self["key_page"].setText("Seite vor/zurück")
			self["key_keypad"].setText("direkt zur Seite…")
		else:
			self["button_page"].hide()
			self["button_keypad"].hide()
			self["key_page"].setText("")
			self["key_keypad"].setText("")

	def handleAvatar(self, url):
		if url and url.startswith("./"):  # in case it's an plugin avatar
			avatarpix = LoadPixmap(cached=True, path=join(self.PLUGINPATH, url.replace("./", "")))
		else:
			filename = join(self.AVATARPATH, f"{url[url.rfind('?avatar=') + 8:].split('.')[0]}.*") if url else join(self.PLUGINPATH, "icons/unknown.png")
			picfiles = glob(filename)  # possibly the file name had to be renamed according to the correct image type
			if picfiles and exists(picfiles[0]):  # use first hit found
				avatarpix = LoadPixmap(cached=True, path=picfiles[0])
				if url in self.avatarDLlist:
					self.avatarDLlist.remove(url)
			else:
				avatarpix = None
				if url not in self.avatarDLlist:  # avoid multiple threaded downloads of equal avatars
					self.avatarDLlist.append(url)
					callInThread(self.downloadAvatar, url)
		return avatarpix

	def downloadAvatar(self, url):
		url = url.encode("ascii", "xmlcharrefreplace").decode().replace(" ", "%20").replace("\n", "")
		file = join(self.AVATARPATH, url[url.rfind("?avatar=") + 8:])
		try:
			response = get(url.encode("utf-8"))
			response.raise_for_status()
			with open(file, "wb") as f:
				f.write(response.content)
			fileparts = file.split(".")
			pictype = what(file)
			if pictype and pictype != fileparts[1]:  # Some avatars could be incorrectly listed as .GIF although they are .JPG or .PNG
				filename = f"{fileparts[0]}.{pictype.replace("jpeg", "jpg")}"
				rename(file, filename)
			self.updateSkin()
		except exceptions.RequestException as error:
			self.downloadError(error)

	def downloadError(self, error):
		self.session.open(MessageBox, f"Der opena.tv Server ist zur Zeit nicht erreichbar.\n{error}", MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)

	def keyOk(self):
		current = self["menu"].getCurrentIndex()
		if self.currmode == "menu":
			self.threadlink = self.threadlinks[current]
			if self.threadlink:
				self.oldmenuindex = current
				callInThread(self.makeThread, movetoend=True)
		else:
			if current < len(self.postlist):
				postdetails = self.postlist[current]
				if postdetails:
					self.session.open(openATVPost, postdetails, self.favmenu)

	def keyExit(self):
		if self.currmode == "menu":
			if exists(self.AVATARPATH):
				rmtree(self.AVATARPATH)
			self.close()
		if self.currmode == "thread":
			if self.favmenu:
				self.close()
			else:  # switch to existing 'menu' view
				self.currmode = "menu"
				self["menu"].style = "default"
				self["headline"].setText("aktuelle Themen")
				self["pagecount"].setText("")
				self.updateSkin()
				self["menu"].setCurrentIndex(self.oldmenuindex)

	def keyGreen(self):
		if self.ready:
			self["menu"].updateList([])
			if self.currmode == "menu":
				callInThread(self.makeMenu)
			elif self.threadlink:
				callInThread(self.makeThread)

	def keyYellow(self):
		if self.favmenu:
			self.session.open(MessageBox, "Dieses Fenster wurde bereits als Favorit geöffnet!\nUm auf die Favoritenliste zurückzukommen, bitte 1x 'Verlassen/Exit' drücken!\n", timeout=5, type=MessageBox.TYPE_INFO, close_on_any_key=True)
		else:
			self.favmenu = True
			self.oldthreadlink = self.threadlink
			self.session.openWithCallback(self.yellow_return, openATVFav)

	def yellow_return(self):
			self.threadlink = self.oldthreadlink
			self.favmenu = False

	def keyRed(self):
		favname, favlink = self.makeFavdata()
		if self.favoriteExists(self.session, favname, favlink):
			self.session.open(MessageBox, f"ABBRUCH!\n\n'{favname}'\n\nist bereits in den Favoriten vorhanden.\n", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
		else:
			self.session.openWithCallback(boundFunction(self.red_return, favname, favlink), MessageBox, f"'{favname}'\n\nzu den Favoriten hinzufügen?\n", MessageBox.TYPE_YESNO, timeout=30)

	def red_return(self, favname, favlink, answer):
		if answer is True:
			self.writeFavorite(self.session, favname, favlink)

	def makeFavdata(self):
		favname, favlink = "", ""
		curridx = self["menu"].getCurrentIndex()
		if self.currmode == "menu":
			if self.maintexts:
				favname = f"THEMA: {self.maintexts[curridx][0]}"
				threadlink = self.threadlinks[curridx]   # threadlink, e.g. https://www.opena.tv/viewtopic.php?t=66608
				threadid = parse_qs(urlparse(threadlink).query)['t'][0]
				if threadid:
					favlink = f"{self.BASEURL}viewtopic.php?t={threadid}&start=0"
		else:
			if self.postlist:
				favname = f"BEITRAG{self.postlist[curridx][2]} von '{self.postlist[curridx][0]}'"
				favlink = f"{self.BASEURL}/viewtopic.php?p={self.postlist[curridx][1]}#p{self.postlist[curridx][1]}"  # postlink, e.g. https://www.opena.tv/viewtopic.php?p=570564#p570564
		return favname, favlink

	def keyDown(self):
		self["menu"].down()

	def keyUp(self):
		self["menu"].up()

	def keyPageDown(self):
		self["menu"].pageDown()

	def keyPageUp(self):
		self["menu"].pageUp()

	def nextPage(self):
		if self.currmode == "menu":
			self.keyPageDown()
		elif self.currmode == "thread" and self.currpage < self.maxpages:
			self.currpage += 1
			threadlink = self.threadlink if self.threadlink else self.threadlinks[self["menu"].getCurrentIndex() - 1]  # use url of previous entry when 'beteiligte Benutzer'
			threadid = parse_qs(urlparse(threadlink).query)['t'][0]
			if threadid:
				self.threadlink = f"{self.BASEURL}viewtopic.php?t={threadid}&start={(self.currpage - 1) * self.POSTSPERTHREAD}"
				callInThread(self.makeThread)

	def prevPage(self):
		if self.currmode == "menu":
			self.keyPageUp()
		elif self.currmode == "thread" and self.currpage > 1:
			self.currpage -= 1
			threadlink = self.threadlink if self.threadlink else self.threadlinks[self["menu"].getCurrentIndex() - 1]  # use url of previous entry when 'beteiligte Benutzer'
			threadid = parse_qs(urlparse(threadlink).query)['t'][0]
			if threadid:
				self.threadlink = f"{self.BASEURL}viewtopic.php?t={threadid}&start={(self.currpage - 1) * self.POSTSPERTHREAD}"
			callInThread(self.makeThread, movetoend=True)

	def gotoPage(self, number):
		if self.currmode == "thread":
			self.session.openWithCallback(self.getKeypad, getNumber, number)

	def getKeypad(self, number):
		if number:
			if number > self.maxpages:
				number = self.maxpages
				self.session.open(MessageBox, f"\nEs sind nur {number} Seiten verfügbar, daher wird die letzte Seite aufgerufen.", MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			threadid = parse_qs(urlparse(self.threadlink).query)['t'][0]
			if threadid:
				self.threadlink = f"{self.BASEURL}viewtopic.php?t={threadid}&start={(number - 1) * self.POSTSPERTHREAD}"
			callInThread(self.makeThread)

	def checkFiles(self):
		try:
			if not exists(self.AVATARPATH):
				makedirs(self.AVATARPATH)
		except OSError as error:
			self.session.open(MessageBox, f"Dateipfad für Avatare konnte nicht neu angelegt werden:\n'{error}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
		favpath = join(self.PLUGINPATH, "db")
		try:
			if not exists(favpath):
				makedirs(favpath)
		except OSError as error:
			self.session.open(MessageBox, f"Dateipfad für Favoriten konnte nicht neu angelegt werden:\n'{error}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
		if not exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN, "w") as f:
					pass  # write empty file
			except OSError as error:
				self.session.open(MessageBox, f"Favoriten konnten nicht neu angelegt werden:\n'{error}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)


def main(session, **kwargs):
	session.open(openATVMain)


def Plugins(**kwargs):
	return [PluginDescriptor(name="OpenATV Reader", description="Das opena.tv Forum bequem auf dem TV mitlesen", where=[PluginDescriptor.WHERE_PLUGINMENU], icon="plugin.png", fnc=main), PluginDescriptor(name="OpenATV Reader", description="Das opena.tv Forum bequem auf dem TV mitlesen", where=[PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main)]
