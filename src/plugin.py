from imghdr import what
from glob import glob
from html import unescape
from os import rename, makedirs, remove, linesep
from os.path import join, exists
from re import search, sub, split, findall, S
from requests import get, exceptions
from six import ensure_binary, ensure_str
from shutil import copy2, rmtree
from twisted.internet.reactor import callInThread
from xml.etree.ElementTree import tostring, parse
from enigma import getDesktop, eTimer, BT_SCALE, BT_KEEP_ASPECT_RATIO
from Components.ActionMap import ActionMap, NumberActionMap
from Components.config import config
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

VERSION = "V1.4"
BASEURL = "https://www.opena.tv/"
AVATARPATH = "/tmp/avatare"
PLUGINPATH = join(resolveFilename(SCOPE_PLUGINS), "Extensions/OpenATVreader/")
FAVORITEN = join(PLUGINPATH, "db/favoriten")


class openATVglobals(Screen):
	def cleanupDescTags(self, text, remove=True):  # remote=True mercilessly cuts the text down to a minimum for MultiContentEntryLines
		if text:
			text = text.replace("<u>", "").replace("</u>", "").replace("<i>", "").replace("</i>", "")
			cutout = search(r'<ul>(.*?)</ul>', text)  # search for listing
			cutout = cutout.group(0) if cutout else "{ERROR}"
			items = findall(r'<li style="">(.*?)</li>', cutout, flags=S)  # search individual items
			listing = ""
			for item in items:
				listing += "• %s\n" % item
			text = sub(r'<ul>.*?</ul>', listing, text)  # exchange listing
			cutout = search(r'<ol\s*class="decimal">(.*?)</ol>', text)  # search for decimal listing
			cutout = cutout.group(0) if cutout else "{ERROR}"
			items = findall(r'<li style="">(.*?)</li>', cutout, flags=S)  # exchange decimal listing
			listing = ""
			for idx, item in enumerate(items):
				listing += "%s. %s\n" % (idx + 1, item)
			text = sub(r'<br\s*/>', "", text).strip()
			text = sub(r'<ol class="decimal">(.*?)</ol>', listing, text)  # search for decimal listing
			text = sub(r'<a.*?href=".*?"\s*target="_blank">(.*?)</a>', "{Link: %s}" % r'\g<1>', text)  # remove links
			text = self.cleanupUserTags(text)
			text = sub(r'<a\s*rel="nofollow".*?</a>', "" if remove else "{Anhang}", text, flags=S)  # remove attachments
			text = sub(r'<a.\s*href=".*?"\s*id="attachment.*?/></a>', "" if remove else "{Bild}", text)  # remove pictures
			text = sub(r'<img\s*src=".*?class="inlineimg"\s*/>', "" if remove else "{Emoicon}", text, flags=S)  # remove EmoIcons
			text = sub(r'<img src=".*?\s*/>', "" if remove else "{Bild}", text)  # remove pictures
			text = sub(r'<iframe class="restrain".*?</iframe>', "" if remove else "\n{Video}\n", text, flags=S)  # remove videos
			text = sub(r'<font\s*size=".*?">(.*?)</font>', r'\g<1>', text, flags=S)  # remove font size
			text = sub(r'<font\s*color=".*?">(.*?)</font>', r'\g<1>', text, flags=S)  # remove font color
			text = sub(r'<span\s*style=.*?>(.*?)</span>', r'\g<1>', text, flags=S)  # remove font style
			text = sub(r'<div class="bbcode_container">\s*<div class="bbcode_description">Code:</div>.*?</div>', "{Code}", text, flags=S)  # remove code
			text = sub(r'<blockquote\s*class="postcontent\s*restore\s*">\s*(.*?)\s*</blockquote>', "", text, flags=S)  # isolate quotes
			text = sub(r'\s*<div\s*class="bbcode_postedby">.*?</div>', "", text, flags=S)  # {start} remove quotes... (the order is important here)
			text = sub(r'\s*<div\s*class="bbcode_quote_container">.*?</div>', "", text, flags=S)
			text = sub(r'\s*<div\s*class="message">(.*?)</div>', "" if remove else "-----{Zitat Anfang}%s\n%s\n%s{Zitat Ende}-----" % ("-" * 117, r'\g<1>', "-" * 120), text, flags=S)  # Zitate isolieren
			text = sub(r'\s*<div\s*class="quote_container">', "", text, flags=S)
			text = sub(r'\s*<div\s*class="bbcode_quote">', "", text, flags=S)
			text = sub(r'<div\s*class="bbcode_container">\s*', "", text, flags=S)  # ...{end} remove quotes
			text = sub(r'<pre\s*class="bbcode_code".*?</pre>', "", text, flags=S)  # remove residual shreds
			text = sub(r'\s*</div>', "", text)  # remove residual shreds
			text = text.replace("{Zitat Ende}-----", "{Zitat Ende}-----\n\n")  # add desired newlines only
			return text if remove else "%s\n" % text
		return ""

	def cleanupUserTags(self, text):
		if text:
			text = sub(r'<b>(.*?)</b>', r'\g<1>', text)  # remove fat marker
			text = sub(r'<strike>(.*?)</strike>', r'\g<1>', text)  # remove strikethrough
			text = sub(r'<font\s*color=".*?">(.*?)</font>', r'\g<1>', text)  # remove font color
			text = sub(r'<marquee\s*direction=".*?" >(.*?)</marquee>', r'\g<1>', text)  # remove marketing tag
			return text.replace("<b>", "").replace("</b>", "").replace("</font>", "")  # remove breaks / newlines / font tag
		return ""

	def searchOneValue(self, regex, text, fallback, flag_S=False):
		text = search(regex, text, flags=S) if flag_S else search(regex, text)
		return text.group(1) if text else fallback

	def searchTwoValues(self, regex, text, fallback1, fallback2, flag_S=False):
		text = search(regex, text, flag_S) if flag_S else search(regex, text)
		return (text.group(1), text.group(2)) if text else (fallback1, fallback2)

	def downloadPage(self, link, file, success, movetoEnd=False):
		link = link.encode("ascii", "xmlcharrefreplace").decode().replace(" ", "%20").replace("\n", "")
		try:
			response = get(ensure_binary(link))
			response.raise_for_status()
			content = response.content
			response.close()
			with open(file, "wb") as f:
				f.write(content)
			if movetoEnd:
				success(movetoEnd)
			else:
				success()
		except exceptions.RequestException as error:
			self.downloadError(error)

	def hideScreen(self):
		if self.hideflag is True and exists("/proc/stb/video/alpha"):
			self.hideflag = False
			for count in range(39, -1, -1):
				with open("/proc/stb/video/alpha", "w") as f:
					f.write("%i" % (config.av.osd_alpha.value * count / 40))
		else:
			self.hideflag = True
			for count in range(1, 41):
				with open("/proc/stb/video/alpha", "w") as f:
					f.write("%i" % (config.av.osd_alpha.value * count / 40))

	def readSkin(self, skin):
		skintext = ""
		try:
			with open(join(PLUGINPATH, "skin_%s.xml") % ("fHD" if getDesktop(0).size().width() > 1300 else "HD"), "r") as fd:
				try:
					domSkin = parse(fd).getroot()
					for element in domSkin:
						if element.tag == "screen" and element.attrib["name"] == skin:
							skintext = ensure_str(tostring(element))
							break
				except Exception as err:
					print("[Skin] Error: Unable to parse skin data in '%s' - '%s'!" % (join(PLUGINPATH, "skin.xml"), err))
		except OSError as err:
			print("[Skin] Error: Unexpected error opening skin file '%s'! (%s)" % (join(PLUGINPATH, "skin.xml"), err))
		return skintext

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


class getNumber(openATVglobals):
	def __init__(self, session, number):
		self.skin = self.readSkin("getNumber")
		Screen.__init__(self, session, self.skin)
		self.field = str(number)
		self["version"] = StaticText(VERSION)
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
		self.field = "%s%s" % (self.field, number)
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
	def __init__(self, session):
		self.skin = self.readSkin("openATVFav")
		Screen.__init__(self, session, self.skin)
		self.hideflag = True
		self.count = 0
		self.favlist = []
		self["version"] = StaticText(VERSION)
		self["headline"] = StaticText("Favoriten")
		self["favmenu"] = List([])
		self["key_red"] = StaticText("Favorit entfernen")
		self["key_yellow"] = StaticText("Favoriten aufrufen")
		self["key_blue"] = StaticText("Ein- / Ausblenden")
		self["actions"] = ActionMap(["OkCancelActions",
									"DirectionActions",
									"ColorActions"], {"ok": self.keyOk,
														"cancel": self.exit,
														"down": self.keyPageDown,
														"up": self.keyPageUp,
														"red": self.keyRed,
														"blue": self.hideScreen}, -1)
		self.onLayoutFinish.append(self.makeFav)

	def makeFav(self):
		self.count = 0
		menutexts = []
		if exists(FAVORITEN):
			try:
				with open(FAVORITEN, "r") as f:
					for line in f.read().split(linesep):
						if "\t" in line:
							self.count += 1
							favline = line.split("\t")
							entry = favline[0].strip()
							link = favline[1].strip()
							self.favlist.append((entry, link))
							entry = "%s: %s" % (entry[:entry.find(":")], entry[entry.find(":") + 1:]) if ":" in entry else entry
							menutexts.append(entry)
			except OSError as error:
				self.session.open(MessageBox, "Favoriten konnten nicht gelesen werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			if not self.count:
				title = "{keine Einträge vorhanden}"
				self.favlist.append((title, "", ""))
				menutexts.append((title))
			self["favmenu"].updateList(menutexts)

	def keyOk(self):
		c = self["favmenu"].getCurrentIndex()
		if self.favlist[c][1]:
			link = self.favlist[c][1]
			if link:
					self.session.open(openATVMain, currlink=link, favmenu=True)

	def keyRed(self):
		if exists(FAVORITEN):
			c = self["favmenu"].getCurrentIndex()
			name = self.favlist[c][0]
			if name and self.favlist[c][1]:
				self.session.openWithCallback(self.red_return, MessageBox, "'%s'\naus den Favoriten entfernen?\n" % name, MessageBox.TYPE_YESNO, timeout=30, default=False)

	def red_return(self, answer):
		if answer is True:
			c = self["favmenu"].getCurrentIndex()
			data = ""
			try:
				with open(FAVORITEN, "r") as f:
					for line in f.read().split("\n"):
						if self.favlist[c][1] not in line and line != "\n":
							data += "%s%s" % (line, linesep)
			except OSError as error:
				self.session.open(MessageBox, "Favoriten konnten nicht gelesen werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			try:
				with open("%s.new" % FAVORITEN, "w") as f:
					f.write(data)
				rename("%s.new" % FAVORITEN, FAVORITEN)
			except OSError as error:
				self.session.open(MessageBox, "Favoriten konnten nicht geschrieben werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			self.favlist = []
			self.makeFav()

	def keyPageDown(self):
		self["favmenu"].down()

	def keyPageUp(self):
		self["favmenu"].up()

	def hideScreen(self):
		if self.hideflag is True and exists("/proc/stb/video/alpha"):
			self.hideflag = False
			count = 40
			while count > 0:
				count -= 1
				with open("/proc/stb/video/alpha", "w") as f:
					f.write("%i" % (config.av.osd_alpha.value * count / 40))
		else:
			self.hideflag = True
			count = 0
			while count < 40:
				count += 1
				with open("/proc/stb/video/alpha", "w") as f:
					f.write("%i" % (config.av.osd_alpha.value * count / 40))

	def exit(self):
		if self.hideflag is False:
			with open("/proc/stb/video/alpha", "w") as f:
				f.write("%i" % config.av.osd_alpha.value)
		self.close()


class openATVPost(openATVglobals):
	def __init__(self, session, currlink, favmenu):
		self.skin = self.readSkin("openATVPost")
		Screen.__init__(self, session, self.skin)
		self.localhtml2 = "/tmp/openatv2.html"
		self.hideflag = True
		self.ready = False
		self.currlink = currlink
		self.favmenu = favmenu
		self.posttitle = ""
		self.menulinks = []
		self["version"] = StaticText(VERSION)
		self["headline"] = StaticText()
		self["postid"] = StaticText()
		self["postnr"] = StaticText()
		self["online"] = Pixmap()
		self["avatar"] = Pixmap()
		self["username"] = StaticText()
		self["utitle"] = StaticText()
		self["rank"] = Pixmap()
		self["postcnt"] = StaticText()
		self["thxgiven"] = StaticText()
		self["thxreceived"] = StaticText()
		self["registered"] = StaticText()
		self["status"] = StaticText()
		self["datum"] = StaticText()
		self["textpage"] = ScrollLabel()
		self["key_red"] = StaticText("Favorit hinzufügen")
		self["key_yellow"] = StaticText("Favoriten aufrufen")
		self["key_blue"] = StaticText("Ein- / Ausblenden")
		self["NumberActions"] = ActionMap(["NumberActions",
												"OkCancelActions",
												"DirectionActions",
												"ChannelSelectBaseActions",
												"MovieSelectionActions",
												"ColorActions"], {"cancel": self.exit,
																	"down": self.keyDown,
																	"up": self.keyUp,
																	"right": self.keyPageDown,
																	"left": self.keyPageUp,
																	"nextBouquet": self.keyPageDown,
																	"prevBouquet": self.keyPageUp,
																	"yellow": self.keyYellow,
																	"red": self.keyRed,
																	"blue": self.hideScreen}, -1)
		self.onLayoutFinish.append(self.onLayoutFinished)

	def onLayoutFinished(self):
		self["headline"].setText("lade gewählten Beitrag...")
		if exists(self.localhtml2):
			self.makePost()
		else:
			callInThread(self.downloadPage, self.currlink, self.localhtml2, self.makePost)

	def makePost(self):
		output = open(self.localhtml2, "rb").read()
		output = ensure_str(output.decode("latin1").encode("utf-8"))
		startpos = output.find(r'<div class="body_wrapper">')
		endpos = output.find(r'<div class="forumBitBoxTBB">')
		cutout = unescape(output[startpos:endpos])
		title = self.searchOneValue(r'<li class="navbit lastnavbit"><span itemprop="title">(.*?)</span></li>', cutout, "", flag_S=True)
		if not title:  # fallback if not found
			title = self.searchOneValue(r'hat auf das Thema.*?">(.*?)</a>\s*im Forum.*?">(.*?)</a>', cutout, "")
		if not title:  # fallback if not found
			title = self.searchOneValue(r'<h2 class="title icon">(.*?)</h2>', cutout, "{ERROR}", flag_S=True)
		self.posttitle = title.strip()
		posts = split(r'<li class="postbitlegacy postbitim postcontainer', cutout, flags=S)[1:]
		for post in posts:
			postid = self.searchOneValue(r'<div id="post_message_(.*?)">', post, "{ERROR}")
			if postid == self.currlink[self.currlink.rfind("#post") + 5:]:
				user = self.cleanupUserTags(self.searchOneValue(r'title=".*?"><strong>(.*?)</strong></a>', post, ""))
				if user and "ForumBot" not in user:
					# for debug purposes only
					# with open("/home/root/logs/atvreader.txt", "w") as f:
					#	f.write(post)
					postnr = self.searchOneValue(r'class="postcounter">#(.*?)</a>', post, "0")
					avatar = self.searchOneValue(r'<img src="(.*?)" alt="Avatar von', post, join(PLUGINPATH, "icons/unknown.png"))
					self.handleIcon(self["avatar"], avatar)
					rank = self.searchOneValue(r'<span class="rank"><img src="(.*?)"\s*alt=', post, "")
					if rank:
						self.handleIcon(self["rank"], rank)
					utitle = self.cleanupUserTags(self.searchOneValue(r'<span class="usertitle">\s*(.*?)\s*</span>', post, "{ERROR}"))
					if "<-" in utitle or "<!-" in utitle or "++" in utitle:
						utitle = ""
					status = self.searchOneValue(r'title="(.*?)"><strong>', post, "")
					statusfile = "icons/online" if "online" in status else "icons/offline"
					self.showPic(self["online"], join(PLUGINPATH, "%s_%s.png" % (statusfile, "fHD" if getDesktop(0).size().width() > 1300 else "HD")), scale=False)
					regi = self.searchOneValue(r'<dt>Registriert seit</dt> <dd>(.*?)</dd>', post, "{ERROR}")
					postcnt = self.searchOneValue(r'<dt>Beiträge</dt>\s*<dd>(.*?)</dd>', post, "{ERROR}")
					tput, tget = self.searchTwoValues(r'<dt>Thanks \(gegeben\)</dt>\s*<dd>(.*?)</dd>\s*<dt>Thanks \(bekommen\)</dt>\s*<dd>(.*?)</dd>', post, "{ERROR}", "{ERROR}")
					date = self.searchTwoValues(r'<span class="date">(.*?)<span class="time">(.*?)</span></span>', post, "{kein Datum}", "{keine Uhrzeit}")
					date = "%s%s" % (date[0], date[1])
					desc = self.searchOneValue(r'<blockquote class="postcontent restore ">(.*?)</blockquote>', post, "{keine Beschreibung}", flag_S=True)
					desc = self.cleanupDescTags(desc, remove=False)
					if date == "{kein Datum}{keine Uhrzeit}" and desc == "{keine Beschreibung}":
						continue
					lastedit = self.searchOneValue(r'<blockquote class="postcontent lastedited">(.*?)</blockquote>', post, "", flag_S=True)
					lastedit = lastedit.strip().replace("\t", "").replace('<span class="time">', "").replace('<span class="reason">', "").replace('</span>', "").split("\n")
					lastedit = list(filter(None, lastedit))  # remove empty entries
					if lastedit:
						desc += "\n\n%s %s" % (lastedit[0], lastedit[1] if len(lastedit) > 1 else "")
					thxqty = self.searchOneValue(r'<span class="postdate">Danke - (.*?) Thanks</span>', post, "", flag_S=True)
					thxfrom = []
					for thx in self.searchOneValue(r'<a href=(.*?)bedankten sich', post, "").split(","):
						thxfound = self.searchOneValue(r'>(.*?)</a>', thx, "").strip()
						if thxfound:
							thxfrom.append(self.cleanupUserTags(self.searchOneValue(r'>(.*?)</a>', thx, "").strip()))
					if thxfrom and thxqty:
						thxfrom = ", ".join(thxfrom)
						desc += "\n\nDanke - %s Thanks  (%s bedankte sich)" % (thxqty, thxfrom) if int(thxqty) == 1 else "\n\nDanke - %s Thanks  (%s bedankten sich)" % (thxqty, thxfrom)
					self["headline"].setText(self.posttitle)
					self["postid"].setText("ID: %s" % postid)
					self["postnr"].setText("#%s" % postnr)
					self["username"].setText(user)
					self["utitle"].setText(utitle)
					self["postcnt"].setText("%s Beiträge" % postcnt)
					self["thxgiven"].setText("%s Thanks gegeben" % tput)
					self["thxreceived"].setText("%s Thanks bekommen" % tget)
					self["status"].setText(status)
					self["registered"].setText("Registriert seit %s" % regi)
					self["datum"].setText("Beitrag von %s Uhr" % date)
					self["textpage"].setText(desc)
		self.ready = True

	def handleIcon(self, widget, link):
		filename = join(AVATARPATH, "%s.*" % link[link.rfind("/") + 1:].split(".")[0])
		picfiles = glob(filename)  # possibly the file name had to be renamed according to the correct image type
		if picfiles and exists(picfiles[0]):  # use first hit found
			self.showPic(widget, picfiles[0])
		else:
			callInThread(self.iconDL, widget, link)

	def iconDL(self, widget, link):
		link = link.encode("ascii", "xmlcharrefreplace").decode().replace(" ", "%20").replace("\n", "")
		filename = join(AVATARPATH, link[link.rfind("/") + 1:])
		try:
			response = get(ensure_binary(link))
			response.raise_for_status()
			content = response.content
			response.close()
			with open(filename, "wb") as f:
				f.write(content)
			fileparts = filename.split(".")
			pictype = what(filename)
			if pictype and pictype != fileparts[1]:  # Some avatars were incorrectly listed as .GIF although they are .JPG or .PNG
				newfname = "%s.%s" % (fileparts[0], pictype.replace("jpeg", "jpg"))
				rename(filename, newfname)
				filename = newfname
			self.showPic(widget, filename)
		except exceptions.RequestException as error:
			self.downloadError(error)

	def downloadError(self, errormsg):
		self.session.open(MessageBox, "Der opena.tv Server ist zur Zeit nicht erreichbar.\n%s" % errormsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)

	def keyYellow(self):
		if self.ready:
			if self.favmenu:
				self.session.open(MessageBox, "Dieses Fenster wurde bereits als Favorit geöffnet!\nUm auf die Favoritenliste zurückzukommen, bitte '2x Verlassen/Exit' drücken!\n", type=MessageBox.TYPE_INFO, timeout=5, close_on_any_key=True)
			else:
				self.session.open(openATVFav)

	def keyRed(self):
		if self.ready and exists(FAVORITEN):
			link = self.currlink
			postid = link[link.find("#post") + 5:] if "#post" in link else "THEMA"
			name = "%s: %s " % (postid, self.posttitle)
			found = False
			if exists(FAVORITEN):
				try:
					with open(FAVORITEN, "r") as f:
						for line in f.read().split("\n"):
							if link in line:
								found = True
								break
				except OSError as error:
					self.session.open(MessageBox, "Favoriten konnten nicht geschrieben werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			if found:
				self.session.open(MessageBox, "ABBRUCH!\n'%s'\n\nist bereits in den Favoriten vorhanden.\n" % name, type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
			else:
				self.session.openWithCallback(self.red_return, MessageBox, "'%s'\n\nzu den Favoriten hinzufügen?\n" % name, MessageBox.TYPE_YESNO, timeout=30)

	def red_return(self, answer):
		if answer is True and exists(FAVORITEN):
			link = self.currlink
			postid = link[link.find("#post") + 5:] if "#post" in link else "THEMA"
			name = "%s: %s " % (postid, self.posttitle)
			try:
				with open(FAVORITEN, "a") as f:
					f.write("%s:%s\t%s%s" % (postid, self.posttitle, link, linesep))
					self.session.open(MessageBox, "'%s'\n\nwurde zu den Favoriten hinzugefügt.\n" % name, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			except OSError as error:
				self.session.open(MessageBox, "Favoriten konnten nicht geschrieben werden:\n'%s'\n" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)

	def keyDown(self):
		self["textpage"].pageDown()

	def keyUp(self):
		self["textpage"].pageUp()

	def keyPageDown(self):
		self["textpage"].pageDown()

	def keyPageUp(self):
		self["textpage"].pageUp()

	def exit(self):
		if self.hideflag is False:
			self.hideflag = True
			with open("/proc/stb/video/alpha", "w") as f:
				f.write("%i" % config.av.osd_alpha.value)
		self.close()


class openATVMain(openATVglobals):
	def __init__(self, session, currlink="", favmenu=False):
		self.skin = self.readSkin("openATVMain")
		Screen.__init__(self, session, self.skin)
		self.currlink = currlink
		self.currmode = "thread" if currlink else "menu"
		self.localhtml = "/tmp/openatv.html"
		self.localhtml2 = "/tmp/openatv2.html"
		self.ready = False
		self.favmenu = favmenu
		self.hideflag = True
		self.count = 1
		self.maxcount = 1
		self.oldlink = ""
		self.menulink = ""
		self.threadlink = ""
		self.titlelist = []
		self.menulinks = []
		self.menutexts = []
		self.menupics = []
		self.avatarDLlist = []
		self["version"] = StaticText(VERSION)
		self["headline"] = StaticText()
		self["button_yellow"] = Label()
		self["button_page"] = Pixmap()
		self["button_keypad"] = Pixmap()
		self["key_red"] = StaticText("Favorit hinzufügen")
		self["key_green"] = StaticText("Alles aktualisieren")
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText("Ein- / Ausblenden")
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
																	"blue": self.hideScreen,
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
																	 "9": self.gotoPage}, -1)

		self.checkFiles()
		linefile = join(PLUGINPATH, "icons/line_%s.png" % ("fHD" if getDesktop(0).size().width() > 1300 else "HD"))
		self.linepix = LoadPixmap(cached=True, path=linefile) if exists(linefile) else None
		statusfile = join(PLUGINPATH, "icons/online_%s.png" % ("fHD" if getDesktop(0).size().width() > 1300 else "HD"))
		self.online = LoadPixmap(cached=True, path=statusfile) if exists(statusfile) else None
		statusfile = join(PLUGINPATH, "icons/offline_%s.png" % ("fHD" if getDesktop(0).size().width() > 1300 else "HD"))
		self.offline = LoadPixmap(cached=True, path=statusfile) if exists(statusfile) else None
		copy2(join(PLUGINPATH, "icons/user_stat.png"), AVATARPATH)
		copy2(join(PLUGINPATH, "icons/unknown.png"), AVATARPATH)
		self.onLayoutFinish.append(self.onLayoutFinished)

	def onLayoutFinished(self):
		self.showPic(self["button_page"], join(PLUGINPATH, "icons/key_updown_%s.png" % ("fHD" if getDesktop(0).size().width() > 1300 else "HD")), show=False, scale=False)
		self.showPic(self["button_keypad"], join(PLUGINPATH, "icons/keypad_%s.png" % ("fHD" if getDesktop(0).size().width() > 1300 else "HD")), show=False, scale=False)
		if self.favmenu:
			self["button_yellow"].hide()
			self["key_yellow"].setText("")
		else:
			self["button_yellow"].show()
			self["key_yellow"].setText("Favoriten aufrufen")
		if self.currlink:
			self.gotoThread()
		else:
			self.gotoMenu()

	def gotoMenu(self):
		self.ready = False
		self.currmode = "menu"
		self["menu"].style = "default"
		self["headline"].setText("lade aktuelle Beiträge...")
		self["pagecount"].setText("")
		self["key_page"].setText("")
		self["key_keypad"].setText("")
		if exists(self.localhtml):
			self.currlink = self.menulink
			self.makeMenu()
		else:
			self.menulink = ""
			callInThread(self.downloadPage, "%sactivity.php" % BASEURL, self.localhtml, self.makeMenu)

	def gotoThread(self):
		self.ready = False
		self.threadlink = ""
		self.currmode = "thread"
		self["menu"].style = "thread"
		self["headline"].setText("lade gewähltes Thema...")
		callInThread(self.downloadPage, self.currlink, self.localhtml2, self.makeThread)

	def makeMenu(self):
		self["headline"].setText("aktuelle Beiträge")
		self.titlelist = []
		self.menulinks = []
		output = open(self.localhtml, "rb").read()
		output = ensure_str(output.decode("latin1").encode("utf-8"))
		startpos = output.find(r'<div class="avatar">')
		endpos = output.find(r'<ul id="footer_links"')
		cutout = unescape(output[startpos:endpos])
		posts = split(r'<div class="avatar">', cutout, flags=S)[1:]
		users = []
		menutexts = []
		menupics = []
		for post in posts:
			user = self.cleanupUserTags(self.searchOneValue(r'<a href=".*?">(.*?)</a>', post, ""))
			if not user or "ForumBot" in user:
				continue
			users.append(user)
			avatar = self.searchOneValue(r'<img src="(.*?)" alt="Avatar von', post, "%simages/styles/TheBeaconLight/misc/unknown.gif" % BASEURL)
			self.handleAvatar(avatar)
			quellen = self.searchTwoValues(r'das Thema.*?">(.*?)</a>\s*im Forum.*?">(.*?)</a>', post, "{kein Thema}", "{kein Forum}")
			self.titlelist.append(quellen[0])
			title = "%s: %s" % (quellen[1], quellen[0])
			desc = self.searchOneValue(r'<div class="excerpt">(.*?)</div>', post, "{keine Beschreibung}", flag_S=True)
			desc = sub(r'\n+\s*\n+', "", desc.replace("<br />", "").replace("\n", "")).strip()
			desc = self.cleanupDescTags(desc)
			date = self.searchTwoValues(r'<span class="date">(.*?)<span class="time">(.*?)</span></span>', post, "{kein Datum}", "{keine Uhrzeit}")
			date = "%s%s" % (date[0], date[1].replace("\\xa", " "))
			stat = self.searchOneValue(r'<div class="views">(.*?) Antwort', post, "0")
			stat = "%s%s" % (stat, " Antwort(en)") if int(stat) > 0 else "neues Thema erstellt"
			link = self.searchOneValue(r'<div class="fulllink"><a href="(.*?)">Weiterlesen</a></div>', post, "")
			link = "%s%s" % (link[:link.find("?s=")], link[link.rfind("#post"):]) if "#post" in link else link[:link.find("?s=")]
			link = "%s%s" % (BASEURL, link) if link else ""
			self.menulinks.append(link)
			menutexts.append([title, desc, date, user, stat])
			menupics.append([avatar, ""])
		users = list(dict.fromkeys(users))  # remove dupes
		userlist = ", ".join(users)
		userlist = "%s…" % userlist[:200] if len(userlist) > 200 or userlist.endswith(",") else userlist
		self.menulinks.append("")
		self.titlelist.append("beteiligte Benutzer")
		menutexts.append(["beteiligte Benutzer", userlist, "", "", ""])
		menupics.append(["icons/user_stat.png", ""])
		self.menutexts = menutexts
		self.menupics = menupics
		self["button_page"].hide()
		self["button_keypad"].hide()
		self.ready = True
		self.updateSkin()

	def makeThread(self, movetoEnd=False):
		self.titlelist = []
		self.menulinks = []
		output = open(self.localhtml2, "rb").read()
		output = ensure_str(output.decode("latin1").encode("utf-8"))
		counters = self.searchTwoValues(r'class="popupctrl">Seite (\d+) von (\d+)</a></span>', output, 1, 1)
		self.count = int(counters[0])
		self.maxcount = int(counters[1])
		title = unescape(self.searchOneValue(r'<title>(.*?)</title>', output, "{kein title}")).strip()
		part = title.split("- Seite")
		self["headline"].setText(part[0])
		self["pagecount"].setText("Seite %s / %s" % (part[1].strip(), self.maxcount) if len(part) > 1 else "Seite 1 / %s" % self.maxcount)
		startpos = output.find(r'<div class="body_wrapper">')
		endpos = output.find(r'<div class="forumBitBoxTBB">')
		cutout = unescape(output[startpos:endpos])
		users = []
		menutexts = []
		menupics = []
		posts = split(r'<li class="postbitlegacy postbitim postcontainer', cutout, flags=S)[1:]
		for post in posts:
			user = self.cleanupUserTags(self.searchOneValue(r'title=".*?"><strong>(.*?)</strong></a>', post, ""))
			if not user or "ForumBot" in user:
				continue
			users.append(self.cleanupUserTags(user))
			avatar = self.searchOneValue(r'<img src="(.*?)" alt="Avatar von', post, "%simages/styles/TheBeaconLight/misc/unknown.gif" % BASEURL)
			avatar = avatar[avatar.find("tv/") + 3:]
			self.handleAvatar(avatar)
			statustext = self.searchOneValue(r'<img class="inlineimg onlinestatus".*?alt="(.*?)"', post, "")
			postcnt = "%s Beiträge" % self.searchOneValue(r'<dt>Beiträge</dt> <dd>(.*?)</dd>', post, "0")
			date = self.searchTwoValues(r'<span class="date">(.*?)<span class="time">(.*?)</span></span>', post, "{kein Datum}", "{keine Uhrzeit}")
			date = "%s%s" % (date[0], date[1].replace("\\xa", " "))
			desc = self.searchOneValue(r'<blockquote class="postcontent restore ">(.*?)</blockquote>', post, "{keine Beschreibung}", flag_S=True)
			desc = self.cleanupDescTags(desc)
			desc = "%s%s…" % (desc[:280], desc[280:desc.find(" ", 280)]) if len(desc) > 280 else desc
			link = self.searchOneValue(r'<a name=".*?" href="(.*?)"', post, "")
			link = "%s%s" % (link[:link.find("?s=")], link[link.rfind("#post"):])
			self.menulinks.append(link)
			self.titlelist.append(title)
			menutexts.append(["", desc, date, user, postcnt])
			menupics.append([avatar, statustext])
		users = list(dict.fromkeys(users))  # remove dupes
		userlist = ", ".join(users)
		userlist = "beteiligte Benutzer\n%s…" % userlist[:200] if len(userlist) > 200 or userlist.endswith(",") else "beteiligte Benutzer\n%s" % userlist
		self.menulinks.append("")
		self.titlelist.append(title)
		menutexts.append(["", userlist, "", "", ""])
		menupics.append(["icons/user_stat.png", ""])
		self.menutexts = menutexts
		self.menupics = menupics
		if self.maxcount == 1:
			self["button_page"].hide()
			self["button_keypad"].hide()
			self["key_page"].setText("")
			self["key_keypad"].setText("")
		else:
			self["button_page"].show()
			self["button_keypad"].show()
			self["key_page"].setText("Seite vor/zurück")
			self["key_keypad"].setText("direkt zur Seite…")
		self.ready = True
		self.updateSkin(movetoEnd)

	def updateSkin(self, movetoEnd=False):
		skinpix = []
		for menupic in self.menupics:
			avatarpix = self.handleAvatar(menupic[0])
			if self.currmode == "thread" and menupic[1]:
				statuspix = self.online if "online" in menupic[1] else self.offline
			else:
				statuspix = None
			skinpix.append([self.linepix, avatarpix, statuspix])
		skinlist = []
		for idx, menulist in enumerate(self.menutexts):
			skinlist.append(tuple(menulist + skinpix[idx]))
		self["menu"].updateList(skinlist)
		if movetoEnd:
			self["menu"].goBottom()
			self["menu"].goLineUp()
		elif self.currlink:
			index = self.menulinks.index(self.currlink) if self.currlink in self.menulinks else 0
			self["menu"].setCurrentIndex(index)
		if self.currmode == "menu":
			self.menulink = self.currlink
		else:
			self.threadlink = self.currlink

	def handleAvatar(self, avatar):
		filename = join(AVATARPATH, "%s.*" % avatar[avatar.rfind("/") + 1:].split(".")[0])
		picfile = glob(filename)  # possibly the file name had to be renamed according to the correct image type
		if picfile and exists(picfile[0]):  # use first hit found
			avatarpix = LoadPixmap(cached=True, path=picfile[0])
			if avatar in self.avatarDLlist:
				self.avatarDLlist.remove(avatar)
		else:
			avatarpix = None
			if avatar not in self.avatarDLlist:  # avoid multiple threaded downloads of equal avatars
				self.avatarDLlist.append(avatar)
				callInThread(self.downloadAvatar, avatar)
		return avatarpix

	def downloadAvatar(self, avatar):
		link = "%s%s" % (BASEURL, avatar)
		link = link.encode("ascii", "xmlcharrefreplace").decode().replace(" ", "%20").replace("\n", "")
		file = join(AVATARPATH, avatar[avatar.rfind("/") + 1:])
		try:
			response = get(ensure_binary(link))
			response.raise_for_status()
			content = response.content
			response.close()
			with open(file, "wb") as f:
				f.write(content)
			fileparts = file.split(".")
			pictype = what(file)
			if pictype and pictype != fileparts[1]:  # Some avatars were incorrectly listed as .GIF although they are .JPG or .PNG
				filename = "%s.%s" % (fileparts[0], pictype.replace("jpeg", "jpg"))
				rename(file, filename)
			self.updateSkin()
		except exceptions.RequestException as error:
			self.downloadError(error)

	def downloadError(self, errormsg):
		self.session.open(MessageBox, "Der opena.tv Server ist zur Zeit nicht erreichbar.\n%s" % errormsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)

	def keyOk(self):
		if self.ready:
			c = self["menu"].getCurrentIndex()
			if self.currmode == "menu":
				self.menulink = self.currlink = self.menulinks[c]
				if self.currlink:
					self.gotoThread()
			else:
				self.threadlink = self.currlink = self.menulinks[c]
				if self.currlink:
					self.session.open(openATVPost, self.currlink, self.favmenu)

	def keyExit(self):
		if self.hideflag is True:
			if self.currmode == "menu":
				if exists(self.localhtml):
					remove(self.localhtml)
				if exists(self.localhtml2):
					remove(self.localhtml2)
				if exists(AVATARPATH):
					rmtree(AVATARPATH)
				self.close()
			else:
				if self.favmenu:
					self.close()
				else:
					self.gotoMenu()
		else:
			with open("/proc/stb/video/alpha", "w") as f:
				f.write("%i" % config.av.osd_alpha.value)

	def keyGreen(self):
		if self.ready:
			self.menulink = ""
			self.threadlink = ""
			self.menulinks = []
			self.titlelist = []
			callInThread(self.downloadPage, "%sactivity.php" % BASEURL, self.localhtml, self.gotoMenu)

	def keyYellow(self):
		if self.ready:
			if self.favmenu:
				self.session.open(MessageBox, "Dieses Fenster wurde bereits als Favorit geöffnet!\nUm auf die Favoritenliste zurückzukommen, bitte 1x 'Verlassen/Exit' drücken!\n", timeout=5, type=MessageBox.TYPE_INFO, close_on_any_key=True)
			else:
				self.favmenu = True
				self.oldlink = self.currlink
				self.session.openWithCallback(self.yellow_return, openATVFav)

	def yellow_return(self):
			self.currlink = self.oldlink
			self.favmenu = False

	def keyRed(self):
		c = self["menu"].getCurrentIndex()
		link = self.menulinks[c]
		if self.ready and link and exists(FAVORITEN):
			postid = link[link.find("#post") + 5:] if "#post" in link else "THEMA"
			title = self.titlelist[c]
			name = "%s: %s " % (postid, title[:title.find(" - Seite")])
			found = False
			if exists(FAVORITEN):
				try:
					with open(FAVORITEN, "r") as f:
						for line in f.read().split("\n"):
							if link in line:
								found = True
								break
				except OSError as error:
					self.session.open(MessageBox, "Favoriten konnten nicht geschrieben werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			if found:
				self.session.open(MessageBox, "ABBRUCH!\n'%s'\n\nist bereits in den Favoriten vorhanden.\n" % name, type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
			else:
				self.session.openWithCallback(self.red_return, MessageBox, "'%s'\n\nzu den Favoriten hinzufügen?\n" % name, MessageBox.TYPE_YESNO, timeout=30)

	def red_return(self, answer):
		if answer is True:
			c = self["menu"].getCurrentIndex()
			link = self.menulinks[c]
			postid = link[link.find("#post") + 5:] if "#post" in link else "THEMA"
			title = self.titlelist[c]
			name = "%s: %s " % (postid, title) if postid else "THEMA: %s" % title
			if exists(FAVORITEN):
				try:
					with open(FAVORITEN, "a") as f:
						f.write("%s:%s\t%s%s" % (postid, title, link, linesep))
					self.session.open(MessageBox, "'%s'\n\nwurde zu den Favoriten hinzugefügt.\n" % name, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
				except OSError as error:
					self.session.open(MessageBox, "Favoriten konnten nicht geschrieben werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)

	def getPosition(self):
		if self.currmode == "menu":
			self.menulink = self.currlink = self.menulinks[self["menu"].getCurrentIndex()]
		else:
			self.threadlink = self.currlink = self.menulinks[self["menu"].getCurrentIndex()]

	def keyDown(self):
		self["menu"].down()
		self.getPosition()

	def keyUp(self):
		self["menu"].up()
		self.getPosition()

	def keyPageDown(self):
		self["menu"].pageDown()
		self.getPosition()

	def keyPageUp(self):
		self["menu"].pageUp()
		self.getPosition()

	def nextPage(self):
		if self.currmode == "menu":
			self.keyPageDown()
		elif self.currmode == "thread" and self.count < self.maxcount:
			currlink = self.currlink if self.currlink else self.menulinks[self["menu"].getCurrentIndex() - 1]  # else use link of previous entry
			self.count += 1
			link = sub(r'-post\d+.*?#post\d+', "-%s.html" % self.count, currlink)
			callInThread(self.downloadPage, link, self.localhtml2, self.makeThread)

	def prevPage(self):
		if self.currmode == "menu":
			self.keyPageUp()
		elif self.currmode == "thread" and self.count > 1:
			currlink = self.currlink if self.currlink else self.menulinks[self["menu"].getCurrentIndex() - 1]  # else use link of previous entry
			self.count -= 1
			link = sub(r'-post\d+.*?#post\d+', "-%s.html" % self.count, currlink)
			callInThread(self.downloadPage, link, self.localhtml2, self.makeThread, movetoEnd=True)

	def gotoPage(self, number):
		if self.currmode == "thread":
			self.session.openWithCallback(self.getKeypad, getNumber, number)

	def getKeypad(self, number):
		if number:
			self.getPosition()
			if number > self.maxcount:
				number = self.maxcount
				self.session.open(MessageBox, "\nEs sind nur %s Seiten verfügbar, daher wird die letzte Seite aufgerufen." % (number), MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			link = "%s.html" % self.currlink[:self.currlink.find("-post")] if number == 1 else sub(r'-post\d+.*?#post\d+', "-%s.html" % number, self.currlink)
			self.ready = False
			self.threadlink = ""
			self.currmode = "thread"
			self["menu"].style = "thread"
			self["headline"].setText("lade gewähltes Thema...")
			callInThread(self.downloadPage, link, self.localhtml2, self.makeThread)

	def checkFiles(self):
		try:
			if not exists(AVATARPATH):
				makedirs(AVATARPATH)
		except OSError as error:
			self.session.open(MessageBox, "Dateipfad für Avatare konnte nicht neu angelegt werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
		favpath = join(PLUGINPATH, "db")
		try:
			if not exists(favpath):
				makedirs(favpath)
		except OSError as error:
			self.session.open(MessageBox, "Dateipfad für Favoriten konnte nicht neu angelegt werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
		if not exists(FAVORITEN):
			try:
				with open(FAVORITEN, "w") as f:
					pass  # write empty file
			except OSError as error:
				self.session.open(MessageBox, "Favoriten konnten nicht neu angelegt werden:\n'%s'" % error, type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)


def main(session, **kwargs):
	session.open(openATVMain)


def Plugins(**kwargs):
	return [PluginDescriptor(name="OpenATV Reader", description="Das opena.tv Forum bequem auf dem TV mitlesen", where=[PluginDescriptor.WHERE_PLUGINMENU], icon="plugin.png", fnc=main), PluginDescriptor(name="OpenATV Reader", description="Das opena.tv Forum bequem auf dem TV mitlesen", where=[PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main)]
