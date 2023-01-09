# -*- coding: utf-8 -*-
from imghdr import what
from glob import glob
from html import unescape
from os import rename, makedirs, remove, linesep
from os.path import join
from re import search, sub, split, findall, S
from requests import get, exceptions
from six import ensure_binary, ensure_str
from twisted.internet.reactor import callInThread
from xml.etree.ElementTree import tostring, parse
from enigma import eListboxPythonMultiContent, eTimer, gFont, loadPNG, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO
from Components.ActionMap import ActionMap, NumberActionMap
from Components.config import config
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaTest
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import fileExists
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

BASEURL = "https://www.opena.tv/"
AVATARPATH = "/var/volatile/tmp/avatars"
PLUGINPATH = join(resolveFilename(SCOPE_PLUGINS), "Extensions/openATV/")
FAVORITEN = join(PLUGINPATH, "db/favoriten")


class openATVglobals(Screen):

	def cleanupDescTags(self, text, remove=True):
		if text:
			text = text.replace("<u>", "").replace("</u>", '').replace("<i>", "").replace("</i>", "")
			bereich = search(r'<ul>(.*?)</ul>', text)  # suche Auflistung
			bereich = bereich.group(0) if bereich else "{ERROR}"
			items = findall(r'<li style="">(.*?)</li>', bereich, flags=S)  # suche Einzelpositionen
			listing = ""
			for item in items:
				listing += "• %s\n" % item
			text = sub(r'<ul>.*?</ul>', listing, text)  # Auflistung austauschen
			bereich = search(r'<ol\s*class="decimal">(.*?)</ol>', text)  # suche dezimale Auflistung
			bereich = bereich.group(0) if bereich else "{ERROR}"
			items = findall(r'<li style="">(.*?)</li>', bereich, flags=S)  # suche Einzelpositionen
			listing = ""
			for idx, item in enumerate(items):
				listing += "%s. %s\n" % (idx + 1, item)
			text = sub(r'<ol class="decimal">(.*?)</ol>', listing, text)  # dezimale Auflistung austauschen
			text = sub(r'<a.*?href="(.*?)"\s*target="_blank">(.*?)</a>', '%s {%s}' % ('\g<2>', '\g<1>'), text)  # Links entfernen
			text = self.cleanupUserTags(text)
			text = sub(r'<a\s*rel="nofollow"\s*href=".*?"</a>', '' if remove else '{Anhang}', text)  # Anhänge entfernen
			text = sub(r'<img\s*src=".*?class="inlineimg"\s*/>', '' if remove else '{Emoicon}', text)  # EmoIcons entfernen
			text = sub(r'<a\s*href=".*?"\s*id="attachment.*?/></a>', '' if remove else '{Bild}', text)  # Bilder entfernen
			text = sub(r'<img src=".*?\s*/>', '' if remove else '{Bild}', text)  # Bilder entfernen
			text = sub(r'<font\s*size=".*?">(.*?)</font>', '\g<1>', text, flags=S)  # Schriftgröße entfernen
			text = sub(r'<blockquote\s*class="postcontent\s*restore\s*">\s*(.*?)\s*</blockquote>', '' if remove else '-----{Zitat Anfang}%s\n{%s}\n%s{Zitat Ende}-----' % ('-' * 90, '\g<1>', '-' * 92), text, flags=S)  # Zitate isolieren
			text = sub(r'<div\s*class="bbcode_postedby">.*?</div>', '', text, flags=S)  # Zitate entfernen... (die Reihenfolge ist hier wichtig)
			text = sub(r'<div\s*class="bbcode_quote_container">.*?</div>', '', text, flags=S)
			text = sub(r'<div\s*class="message">(.*?)</div>', '' if remove else '\n-----{Zitat Anfang}%s\n{%s}\n%s{Zitat Ende}-----\n' % ('-' * 90, '\g<1>', '-' * 92), text, flags=S)  # Zitate isolieren
			text = sub(r'<div\s*class="quote_container">', '', text, flags=S)
			text = sub(r'<div\s*class="bbcode_quote">', '', text, flags=S)
			text = sub(r'<div\s*class="bbcode_container">', '', text, flags=S)  # ...Zitate entfernen
			text = sub(r'<pre\s*class="bbcode_code".*?</pre>', '', text, flags=S)  # Restfetzen entfernen
			text = sub(r'\s*</div>\s*', '', text)  # Restfetzen entfernen
			text = sub(r"<br\s*/>", "", text).replace("\n\n", "\n").strip()  # Umbrüche entfernen
			return text
		return ""

	def cleanupUserTags(self, text):
		if text:
			text = sub(r"<b>(.*?)</b>", '\g<1>', text)  # Fettmarkierung entfernen
			text = sub(r'<strike>(.*?)</strike>', '\g<1>', text)  # Durchgestrichenes entfernen
			text = sub(r'<font\s*color=".*?">(.*?)</font>', '\g<1>', text)  # Schriftfarbe entfernen
			text = sub(r'<marquee\s*direction=".*?" >(.*?)</marquee>', '\g<1>', text)  # Marketing-Tag entfernen
			return text.replace("<b>", "").replace("</b>", "")  # Umbrüche entfernen
		return ""

	def searchOneValue(self, regex, text, fallback, flag_S=False):
		text = search(regex, text, flags=S) if flag_S else search(regex, text)
		return text.group(1) if text else fallback

	def searchTwoValues(self, regex, text, fallback1, fallback2, flag_S=False):
		text = search(regex, text, flag_S) if flag_S else search(regex, text)
		return (text.group(1), text.group(2)) if text else (fallback1, fallback2)

	def downloadMissingAvatars(self, links):
		if not fileExists(AVATARPATH):
			makedirs(AVATARPATH)
		for link in links:
			realname = glob(join(AVATARPATH, "%s%s" % (link[link.rfind("/") + 1:link.rfind(".")], ".*")))
			if not realname or not fileExists(realname[0]):
				self.downloadIcon("%s%s" % (BASEURL, link), join(AVATARPATH, link[link.rfind("/") + 1:]))

	def threadGetPage(self, link, success):
		link = link.encode('ascii', 'xmlcharrefreplace').decode().replace(' ', '%20').replace('\n', '')
		try:
			response = get(ensure_binary(link))
			response.raise_for_status()
			success(response.content)
		except exceptions.RequestException as error:
			self.downloadError(error)

	def threadDownloadPage(self, link, file, success):
		link = link.encode('ascii', 'xmlcharrefreplace').decode().replace(' ', '%20').replace('\n', '')
		try:
			response = get(ensure_binary(link))
			response.raise_for_status()
			with open(file, "wb") as f:
				f.write(response.content)
			success(file)
		except exceptions.RequestException as error:
			self.downloadError(error)

	def downloadIcon(self, link, filename):
		link = link.encode('ascii', 'xmlcharrefreplace').decode().replace(' ', '%20').replace('\n', '')
		try:
			response = get(ensure_binary(link))
			response.raise_for_status()
			with open(filename, "wb") as f:
				f.write(response.content)
			pictype = what(filename).replace("jpeg", "jpg")  # ToDo: muß noch umgestellt & entfernt werden
			filetype = filename[:filename.rfind(".") + 1:]
			if filetype != pictype:
				rename(filename, "%s%s" % (filename[:filename.rfind(".") + 1], pictype))
		except exceptions.RequestException as error:
			self.downloadError(error)

	def downloadError(self, errormsg):
		self.session.open(MessageBox, '\nDer opena.tv Server ist zur Zeit nicht erreichbar.\n%s' % errormsg, MessageBox.TYPE_INFO, close_on_any_key=True)

	def hideScreen(self):
		if self.hideflag is True and fileExists('/proc/stb/video/alpha'):
			self.hideflag = False
			count = 40
			while count > 0:
				count -= 1
				f = open('/proc/stb/video/alpha', 'w')
				f.write('%i' % (config.av.osd_alpha.value * count / 40))
				f.close()
		else:
			self.hideflag = True
			count = 0
			while count < 40:
				count += 1
				f = open('/proc/stb/video/alpha', 'w')
				f.write('%i' % (config.av.osd_alpha.value * count / 40))
				f.close()

	def readSkin(self, skin):
		skintext = ""
		try:
			with open(join(PLUGINPATH, "skin.xml"), "r") as fd:
				try:
					domSkin = parse(fd).getroot()
					for element in domSkin:
						if element.tag == "screen" and element.attrib['name'] == skin:
							skintext = ensure_str(tostring(element))
							break
				except Exception as err:
					print("[Skin] Error: Unable to parse skin data in '%s' - '%s'!" % (join(PLUGINPATH, "skin.xml"), err))
		except OSError as err:
			print("[Skin] Error: Unexpected error opening skin file '%s'! (%s)" % (join(PLUGINPATH, "skin.xml"), err))
		return skintext


class openATVThread(openATVglobals):
	def __init__(self, session, link, fav, new):
		self.skin = self.readSkin("openATVThread")
		Screen.__init__(self, session, self.skin)
		self.toogleHelp = self.session.instantiateDialog(helpScreen)
		self.showhelp = False
		self.localhtml2 = '/tmp/openatv2.html'
		self.picfile = '/tmp/openatv.jpg'
		self.hideflag = True
		self.closed = False
		self.favmenu = True
		self.lastpage = True
		self.ready = False
		self.link = link
		self.fav = fav
		self.new = new
		self.count = 1
		self.maxcount = 1
		self.postcount = 1
		self.maxpostcount = 1
		self.threadtitle = ''
		self.postlink = ''
		self.titellist = []
		self.threadlink = []
		self.threadentries = []
		self.current = 'menu'
		self['menu'] = ItemList([])
		self['menu'].hide()
		self['textpage'] = ScrollLabel('')
		self['textpage'].hide()
		self['headline'] = Label('')
		self['postid'] = Label('')
		self['postnr'] = Label('')
		self['avatar'] = Pixmap()
		self['avatar'].hide()
		self['ranks'] = Pixmap()
		self['ranks'].hide()
		self['line1'] = Pixmap()
		self['line1'].hide()
		self['line2'] = Pixmap()
		self['line2'].hide()
		self['user'] = Label('')
		self['status'] = Label('')
		self['postcnt'] = Label('')
		self['thxgiven'] = Label('')
		self['thxreceived'] = Label('')
		self['registered'] = Label('')
		self['datum'] = Label('')
		self['NumberActions'] = NumberActionMap(['NumberActions',
		 'OkCancelActions',
		 'DirectionActions',
		 'ColorActions',
		 'ChannelSelectBaseActions',
		 'MovieSelectionActions',
		 'HelpActions'], {'ok': self.ok,
		 'cancel': self.exit,
		 'down': self.down,
		 'up': self.up,
		 'right': self.rightDown,
		 'left': self.leftUp,
		 'nextBouquet': self.nextPage,
		 'prevBouquet': self.prevPage,
		 '0': self.gotoPage,
		 '1': self.gotoPage,
		 '2': self.gotoPage,
		 '3': self.gotoPage,
		 '4': self.gotoPage,
		 '5': self.gotoPage,
		 '6': self.gotoPage,
		 '7': self.gotoPage,
		 '8': self.gotoPage,
		 '9': self.gotoPage,
		 'yellow': self.yellow,
		 'red': self.red,
		 'blue': self.hideScreen,
		 'showEventInfo': self.showHelp}, -1)
		self.onLayoutFinish.append(self.onLayoutFinished)

	def onLayoutFinished(self):
		self['headline'].setText("lade und verarbeite gewähltes Thema...")
		if self.fav is True:
			if search(r'www.opena.tv/forum.*?-\d+.html', self.link) is not None:
				self.favmenu = True
				callInThread(self.threadDownloadPage, self.link, self.localhtml2, self.makeThreadView)
			else:
				self.postlink = self.link
				callInThread(self.threadGetPage, self.postlink, self.makePostviewPage)
		else:
			callInThread(self.threadDownloadPage, self.link, self.localhtml2, self.makeThreadView)

	def makeThreadView(self, string):
		output = open(self.localhtml2, 'rb').read()
		output = ensure_str(output.decode('latin1').encode('utf-8'))
		counters = self.searchTwoValues(r'class="popupctrl">Seite (\d+) von (\d+)</a></span>', output, 1, 1)
		self.count = int(counters[0])
		self.maxcount = int(counters[1])
		title = unescape(self.searchOneValue(r'<title>(.*?)</title>', output, "{kein Titel}"))
		title = "%s - Seite 1 von %s" % (title, self.maxcount) if title.find("Seite") == -1 else "%s von %s" % (title, self.maxcount)
		self.threadtitle = title
		self.setTitle(title)
		startpos = output.find('<div class="body_wrapper">')
		endpos = output.find('<div style="clear:both;"></div>')
		bereich = unescape(output[startpos:endpos])
		users = []
		logos = []
		pcnts = []
		dates = []
		descs = []
		links = []
		posts = split(r'<div class="posthead">', bereich, flags=S)
		for post in posts:
			user = self.searchOneValue(r'title=".*?"><strong>(.*?)</strong></a>', post, None)
			if not user or "ForumBot" in user:
				continue
			users.append(self.cleanupUserTags(user))
			logo = self.searchOneValue(r'<img src="(.*?)" alt="Avatar von', post, "%simages/styles/TheBeaconLight/misc/unknown.gif" % BASEURL)
			logos.append(logo[logo.find("tv/") + 3:])
			pcnts.append(self.searchOneValue(r'<dt>Beiträge</dt> <dd>(.*?)</dd>', post, "0"))
			date = self.searchTwoValues(r'<span class="date">(.*?)<span class="time">(.*?)</span></span>', post, "{kein Datum}", "{keine Uhrzeit}")
			dates.append("%s%s" % (date[0], date[1]))
			desc = self.searchOneValue(r'<blockquote class="postcontent restore ">(.*?)</blockquote>', post, "{keine Beschreibung}", flag_S=True)
			desc = self.cleanupDescTags(desc).replace("\n", " ")
			desc = "%s%s…" % (desc[:300], desc[300:desc.find(" ", 300)]) if len(desc) > 300 else desc
			descs.append(desc)
			links.append(self.searchOneValue(r'<a name=".*?" href="(.*?)" class="postcounter">', post, None))
		self['headline'].setText("lade fehlende Avatare...")
		self.downloadMissingAvatars(logos)
		self['headline'].setText(title)
		for i, user in enumerate(users):
			res = ['']
			res.append(MultiContentEntryText(pos=(0, 0), size=(1800, 135), font=-1, backcolor=1381651, backcolor_sel=1381651, flags=RT_HALIGN_LEFT, text=''))
			res.append(MultiContentEntryPixmapAlphaTest(pos=(0, 0), size=(1800, 7), png=loadPNG(join(PLUGINPATH, "pic/line.png"))))
			realname = glob(join(AVATARPATH, "%s%s" % (logos[i][logos[i].rfind("/") + 1:logos[i].rfind(".")], ".*")))
			if realname:
				res.append(MultiContentEntryPixmapAlphaTest(pos=(7, 15), size=(108, 108), backcolor=1381651, backcolor_sel=1381651, png=LoadPixmap(realname[0]), flags=BT_SCALE | BT_KEEP_ASPECT_RATIO))
			res.append(MultiContentEntryText(pos=(135, 12), size=(1655, 58), font=-1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_LEFT, text=title))
			res.append(MultiContentEntryText(pos=(135, 15), size=(1290, 105), font=0, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_LEFT | RT_WRAP, text=descs[i]))
			res.append(MultiContentEntryText(pos=(1440, 7), size=(315, 40), font=1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_RIGHT, text=dates[i]))
			res.append(MultiContentEntryText(pos=(1440, 45), size=(315, 40), font=-1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_RIGHT, text=user))
			res.append(MultiContentEntryText(pos=(1440, 90), size=(315, 40), font=1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_RIGHT, text="%s Beiträge" % pcnts[i]))
			self.threadentries.append(res)
			self.threadlink.append(links[i])
			self.titellist.append(title)
			userlist = ", ".join([*set(users)])
			userlist = "%s…" % userlist[:200] if len(userlist) > 200 else userlist
		res = ['']
		res.append(MultiContentEntryText(pos=(0, 0), size=(1800, 135), font=-1, backcolor=1381651, backcolor_sel=1381651, flags=RT_HALIGN_LEFT, text=''))
		res.append(MultiContentEntryPixmapAlphaTest(pos=(0, 0), size=(1800, 7), png=loadPNG(join(PLUGINPATH, "pic/line.png"))))
		res.append(MultiContentEntryPixmapAlphaTest(pos=(5, 10), size=(108, 108), backcolor=1381651, backcolor_sel=1381651, png=LoadPixmap(join(PLUGINPATH, "pic/user_stat.png")), flags=BT_SCALE | BT_KEEP_ASPECT_RATIO))
		res.append(MultiContentEntryText(pos=(135, 12), size=(1290, 40), font=-1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_LEFT, text='beteiligte Benutzer'))
		res.append(MultiContentEntryText(pos=(135, 57), size=(1620, 86), font=0, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_LEFT | RT_WRAP, text=userlist))
		res.append(MultiContentEntryPixmapAlphaTest(pos=(89, 0), size=(1800, 7), png=loadPNG(join(PLUGINPATH, "pic/line.png"))))
		index = links.index(self.link) if self.link in links else 0
		self.threadentries.append(res)
		self.threadlink.append(None)
		self.titellist.append('beteiligte Benutzer')
		self['menu'].l.setList(self.threadentries)
		self['menu'].l.setItemHeight(135)
		self['menu'].moveToIndex(index)
		self['menu'].show()
		self.ready = True

	def makePostviewPage(self, output):
		self.current = 'postview'
		self.favmenu = False
		self['menu'].hide()
		self['avatar'].hide()
		self['ranks'].hide()
		output = ensure_str(output.decode('latin1').encode('utf-8'))
		startpos = output.find('<div class="body_wrapper">')
		endpos = output.find('<div style="clear:both;"></div>')
		bereich = unescape(output[startpos:endpos])
		postcount = search(r'class="popupctrl">Seite (\d+) von (\d+)</a></span>', bereich)
		if postcount:
			self.postcount = int(postcount.group(1))
			self.maxpostcount = int(postcount.group(2))
		title = search(r'<li class="navbit lastnavbit"><span itemprop="title">(.*?)</span></li>', bereich, flags=S)
		if not title:  # fallback
			title = search(r'hat auf das Thema.*?">(.*?)</a>\s*im Forum.*?">(.*?)</a>', bereich)
		if not title:  # fallback
			title = search(r'<h2 class="title icon">(.*?)</h2>', bereich, flags=S)
		title = title.group(1).strip() if title else "{ERROR}"
		title = "%s…" % title[:60] if len(title) > 60 else title
		posts = split(r'<div class="posthead">', bereich, flags=S)
		for post in posts:
			postid = self.searchOneValue(r'<div id="post_message_(.*?)">', post, "{ERROR}")
			if postid == self.postlink[self.postlink.rfind("#post") + 5:]:
				user = self.cleanupUserTags(self.searchOneValue(r'title=".*?"><strong>(.*?)</strong></a>', post, None))
				if user and "ForumBot" not in user:
					logo = self.searchOneValue(r'<img src="(.*?)" alt="Avatar von', post, join(PLUGINPATH, "pic/unknown.png"))
					self['headline'].setText("lade fehlenden Avatar...")
					self.downloadMissingAvatars([logo])
					realname = glob(join(AVATARPATH, "%s%s" % (logo[logo.rfind("/") + 1:logo.rfind(".")], ".*")))
					if realname:
						self.showPic(self['avatar'], realname[0])
					rank = self.searchOneValue(r'<span class="rank"><img src="(.*?)"\s*alt=', post, None)
					if rank:
						filename = join(AVATARPATH, rank[rank.rfind("/") + 1:])
						if not fileExists(filename):
							self.downloadIcon(rank, filename)
						self.showPic(self['ranks'], filename)
					stat = self.searchOneValue(r'<span class="usertitle">\s*(.*?)\s*</span>', post, "{ERROR}")
					if "<-" in stat or "<!-" in stat or "++" in stat:
						self['status'].hide()
					else:
						self['status'].setText(stat)
						self['status'].show()
					self['headline'].setText(title)
					postnr = self.searchOneValue(r'class="postcounter">#(.*)</a><a id=', post, "{ERROR}")
					regi = self.searchOneValue(r'<dt>Registriert seit</dt> <dd>(.*?)</dd>', post, "{ERROR}")
					pcnt = self.searchOneValue(r'<dt>Beiträge</dt>\s*<dd>(.*?)</dd>', post, "{ERROR}")
					tput, tget = self.searchTwoValues(r'<dt>Thanks \(gegeben\)</dt>\s*<dd>(.*?)</dd>\s*<dt>Thanks \(bekommen\)</dt>\s*<dd>(.*?)</dd>', post, "{ERROR}", "{ERROR}")
					date = self.searchTwoValues(r'<span class="date">(.*?)<span class="time">(.*?)</span></span>', post, "{kein Datum}", "{keine Uhrzeit}")
					date = "%s%s" % (date[0], date[1])
					desc = self.searchOneValue(r'<blockquote class="postcontent restore ">(.*?)</blockquote>', post, "{keine Beschreibung}", flag_S=S)
					desc = self.cleanupDescTags(desc, remove=False)
					last = search(r'<blockquote class="postcontent lastedited">(.*?)\s*(Heute um <span class="time">(.*?)</span> Uhr)', post, flags=S)
					desc += "\n\n%s\n%sHeute um %s Uhr)" % ("_" * 45, last.group(1).strip(), last.group(3)) if last else ""
					break
		self['line1'].show()
		self['line2'].show()
		self['postid'].setText("ID: %s" % postid)
		self['postid'].show()
		self['postnr'].setText("#%s" % postnr)
		self['postnr'].show()
		self['user'].setText(user)
		self['user'].show()
		self['postcnt'].setText("%s Beiträge" % pcnt)
		self['postcnt'].show()
		self['thxgiven'].setText("%s Thanks gegeben" % tput)
		self['thxgiven'].show()
		self['thxreceived'].setText("%s Thanks bekommen" % tget)
		self['thxreceived'].show()
		self['registered'].setText("Registriert seit %s" % regi)
		self['registered'].show()
		self['datum'].setText("Beitrag von %s Uhr" % date)
		self['datum'].show()
		self['textpage'].setText(desc)
		self['textpage'].show()
		if self.lastpage is True:
			self['textpage'].lastPage()
			self['textpage'].pageUp()

	def showPic(self, pixmap, filename):
		try:  # für openATV 7.x
			pixmap.instance.setPixmapScaleFlags(BT_SCALE | BT_KEEP_ASPECT_RATIO)
			pixmap.instance.setPixmapFromFile(filename)
		except:  # für openATV 6.x
			currPic = LoadPixmap(filename)
			pixmap.instance.setScale(1)
			pixmap.instance.setPixmap(currPic)
		pixmap.show()

	def ok(self):
		if self.current == 'menu':
			try:
				c = self['menu'].getSelectedIndex()
				self.postlink = self.threadlink[c]
				callInThread(self.threadGetPage, self.postlink, self.makePostviewPage)
			except IndexError:
				pass

	def yellow(self):
		if self.ready is True:
			self.session.open(openATVFav)

	def red(self):
		if self.ready is True:
			c = self['menu'].getSelectedIndex()
			name = self.titellist[c]
			link = self.threadlink[c]
			if search(r'www.opena.tv/forum.*?-\d+.html', link) is not None:
				self.session.openWithCallback(self.red_return, MessageBox, "\nForum\n'%s'\nzu den Favoriten hinzufügen?" % name, MessageBox.TYPE_YESNO)
			else:
				self.session.openWithCallback(self.red_return, MessageBox, "\nThread\n'%s'\nzu den Favoriten hinzufügen?" % name, MessageBox.TYPE_YESNO)

	def red_return(self, answer):
		if answer is True:
			c = self['menu'].getSelectedIndex()
			if fileExists(FAVORITEN):
				f = open(FAVORITEN, 'a')
				link = self.threadlink[c]
				if search(r'www.opena.tv/forum\d+', link) is not None:
					data = "Forum: %s:::%s" % (self.titellist[c], self.menulink[c])
				else:
					data = "Thread: %s:::%s" % (self.titellist[c], self.threadlink[c])
				f.write(data)
				f.write(linesep)
				f.close()
		self.session.open(openATVFav)

	def nextPage(self):
		if self.current == 'menu':
			if self.count < self.maxcount:
				self.count += 1
				link = sub(r'-post\d+.*?#post\d+', '-%s.html' % self.count, self.link)
				self.titellist = []
				self.threadlink = []
				self.threadentries = []
				self['menu'].hide()
				callInThread(self.threadDownloadPage, link, self.localhtml2, self.makeThreadView)

	def prevPage(self):
		if self.current == 'menu':
			if self.count > 1:
				self.count -= 1
				link = sub(r'-post\d+.*?#post\d+', '-%s.html' % self.count, self.link)
				self.titellist = []
				self.threadlink = []
				self.threadentries = []
				self['menu'].hide()
				callInThread(self.threadDownloadPage, link, self.localhtml2, self.makeThreadView)

	def gotoPage(self, number):
		self.session.openWithCallback(self.numberEntered, getNumber, number)

	def numberEntered(self, number):
		if self.current == 'menu':
			if number is None or number == 0:
				pass
			else:
				if int(number) > self.maxcount:
					number = self.maxcount
					self.session.open(MessageBox, '\nNur %s Seiten verfügbar. Gehe zu Seite %s.' % (number, number), MessageBox.TYPE_INFO, close_on_any_key=True)
				self.count = int(number)
				link = sub(r'-post\d+.*?#post\d+', '-%s.html' % self.count, self.link)
				self.titellist = []
				self.threadlink = []
				self.threadentries = []
				self['menu'].hide()
				callInThread(self.threadDownloadPage, link, self.localhtml2, self.makeThreadView)
		elif number is None or number == 0:
			pass
		else:
			self.lastpage = False
			if int(number) > self.maxpostcount:
				number = self.maxpostcount
				if number > 1:
					self.session.open(MessageBox, '\nNur %s Seiten verfügbar. Gehe zu Seite %s.' % (number, number), MessageBox.TYPE_INFO, close_on_any_key=True)
				else:
					self.session.open(MessageBox, '\nNur %s Seite verfügbar. Gehe zu Seite %s.' % (number, number), MessageBox.TYPE_INFO, close_on_any_key=True)
			self.postcount = int(number)
			link = sub(r'-post\d+.*?#post\d+', '-%s.html' % self.postcount, self.postlink)
			callInThread(self.threadGetPage, link, self.makePostviewPage)

	def showHelp(self):
		if self.showhelp is False:
			self.showhelp = True
			self.toogleHelp.show()
		else:
			self.showhelp = False
			self.toogleHelp.hide()

	def selectMenu(self):
		self['menu'].selectionEnabled(1)

	def down(self):
		if self.current == 'menu':
			self['menu'].down()
		else:
			self['textpage'].pageDown()

	def up(self):
		if self.current == 'menu':
			self['menu'].up()
		else:
			self['textpage'].pageUp()

	def rightDown(self):
		if self.current == 'menu':
			self['menu'].pageDown()
		else:
			self['textpage'].pageDown()

	def leftUp(self):
		if self.current == 'menu':
			self['menu'].pageUp()
		else:
			self['textpage'].pageUp()

	def exit(self):
		if self.hideflag is False:
			self.hideflag = True
			f = open('/proc/stb/video/alpha', 'w')
			f.write('%i' % config.av.osd_alpha.value)
			f.close()
		if self.showhelp is True:
			self.showhelp = False
			self.toogleHelp.hide()
		elif self.current == 'returnmenu':
			self.current = "menu"
		elif self.fav is True or self.current == 'menu':
			self.session.deleteDialog(self.toogleHelp)
			self.close()
		elif self.current == 'postview':
			self['line1'].hide()
			self['line2'].hide()
			self['avatar'].hide()
			self['ranks'].hide()
			self['postid'].hide()
			self['postnr'].hide()
			self['user'].hide()
			self['status'].hide()
			self['postcnt'].hide()
			self['thxgiven'].hide()
			self['thxreceived'].hide()
			self['registered'].hide()
			self['datum'].hide()
			self['textpage'].hide()
			self['menu'].show()
			if self.favmenu is True:
				self.current = 'menu'
				self.setTitle(self.threadtitle)
				self.lastpage = True
			else:
				self.current = 'returnmenu'
				self.setTitle(self.threadtitle)
				self['headline'].setText(self.threadtitle)
				self.lastpage = True


class getNumber(openATVglobals):
	def __init__(self, session, number):
		self.skin = self.readSkin("getNumber")
		Screen.__init__(self, session, self.skin)
		self.field = str(number)
		self['number'] = Label(self.field)
		self['actions'] = NumberActionMap(['SetupActions'], {'cancel': self.quit,
		 'ok': self.keyOK,
		 '1': self.keyNumber,
		 '2': self.keyNumber,
		 '3': self.keyNumber,
		 '4': self.keyNumber,
		 '5': self.keyNumber,
		 '6': self.keyNumber,
		 '7': self.keyNumber,
		 '8': self.keyNumber,
		 '9': self.keyNumber,
		 '0': self.keyNumber})
		self.Timer = eTimer()
		self.Timer.callback.append(self.keyOK)
		self.Timer.start(2000, True)

	def keyNumber(self, number):
		self.Timer.start(2000, True)
		self.field = "%s%s" % (self.field, number)
		self['number'].setText(self.field)
		if len(self.field) >= 4:
			self.keyOK()

	def keyOK(self):
		self.Timer.stop()
		self.close(int(self['number'].getText()))

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
		self.favlink = []
		self.faventries = []
		self['favmenu'] = ItemList([])
		self['label'] = Label('= Favorit löschen')
		self['actions'] = ActionMap(['OkCancelActions', 'DirectionActions', 'ColorActions'], {'ok': self.ok,
		 'cancel': self.exit,
		 'down': self.down,
		 'up': self.up,
		 'red': self.red,
		 'blue': self.hideScreen}, -1)
		self.makeFav()

	def makeFav(self):
		self.setTitle('openATV:::Favoriten')
		if fileExists(FAVORITEN):
			f = open(FAVORITEN, 'r')
			for line in f:
				if ':::' in line:
					self.count += 1
					favline = line.split(r':::')
					titel = str(favline[0])
					link = favline[1].replace('\n', '')
					res = ['']
					res.append(MultiContentEntryText(pos=(0, 0), size=(1800, 67), font=-1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_CENTER | RT_VALIGN_CENTER, text=titel))
					self.faventries.append(res)
					self.favlist.append(titel)
					self.favlink.append(link)
			f.close()
			self['favmenu'].l.setList(self.faventries)
			self['favmenu'].l.setItemHeight(45)

	def ok(self):
		c = self.getIndex(self['favmenu'])
		link = self.favlink[c]
		self.session.openWithCallback(self.exit, openATVThread, link, True, False)

	def red(self):
		if len(self.favlist) > 0:
			c = self.getIndex(self['favmenu'])
			name = self.favlist[c]
			self.session.openWithCallback(self.red_return, MessageBox, "\n'%s'\naus den Favoriten entfernen?" % name, MessageBox.TYPE_YESNO)

	def red_return(self, answer):
		if answer is True:
			c = self.getIndex(self['favmenu'])
			link = self.favlink[c]
			data = ''
			f = open(FAVORITEN, 'r')
			for line in f:
				if link not in line and line != '\n':
					data += line
			f.close()
			fnew = open("%s.new" % FAVORITEN, 'w')
			fnew.write(data)
			fnew.close()
			rename("%s.new" % FAVORITEN, FAVORITEN)
			self.favlist = []
			self.favlink = []
			self.faventries = []
			self.makeFav()

	def getIndex(self, list):
		return list.getSelectedIndex()

	def down(self):
		self['favmenu'].down()

	def up(self):
		self['favmenu'].up()

	def hideScreen(self):
		if self.hideflag is True and fileExists('/proc/stb/video/alpha'):
			self.hideflag = False
			count = 40
			while count > 0:
				count -= 1
				f = open('/proc/stb/video/alpha', 'w')
				f.write('%i' % (config.av.osd_alpha.value * count / 40))
				f.close()

		else:
			self.hideflag = True
			count = 0
			while count < 40:
				count += 1
				f = open('/proc/stb/video/alpha', 'w')
				f.write('%i' % (config.av.osd_alpha.value * count / 40))
				f.close()

	def exit(self):
		if self.hideflag is False:
			f = open('/proc/stb/video/alpha', 'w')
			f.write('%i' % config.av.osd_alpha.value)
			f.close()
		self.close()


class helpScreen(openATVglobals):
	def __init__(self, session):
		self.skin = self.readSkin("helpScreen")
		Screen.__init__(self, session, self.skin)
		self['label_red'] = Label('Favorit hinzufügen')
		self['label_green'] = Label('Alles aktualisieren')
		self['label_yellow'] = Label('Favoriten aufrufen')
		self['label_blue'] = Label('Ein- / Ausblenden')
		self['label1'] = Label('Bouquet = +/- Seite')
		self['label2'] = Label('  0 - 999 = Seite')
		self['actions'] = ActionMap(['OkCancelActions'], {'ok': self.close, 'cancel': self.close}, -1)


class ItemList(MenuList):
	def __init__(self, items, enableWrapAround=True):
		MenuList.__init__(self, items, enableWrapAround, eListboxPythonMultiContent)
		self.l.setFont(-1, gFont('Regular', 33))
		self.l.setFont(0, gFont('Regular', 30))
		self.l.setFont(1, gFont('Regular', 27))
		self.l.setFont(2, gFont('Regular', 24))


class openATVMain(openATVglobals):
	def __init__(self, session):
		self.skin = self.readSkin("openATVMain")
		Screen.__init__(self, session, self.skin)
		self.toogleHelp = self.session.instantiateDialog(helpScreen)
		self.showhelp = False
		self.localhtml = '/tmp/openatv.html'
		self.localhtml2 = '/tmp/openatv2.html'
		self.picfile = '/tmp/openatv.jpg'
		self.menuentries = []
		self.menulink = []
		self.titellist = []
		self.hideflag = True
		self.ready = False
		self['menu'] = ItemList([])
		self['menu'].hide()
		self['user'] = ScrollLabel('')
		self['user'].hide()
		self['headline'] = Label('')
		self['actions'] = ActionMap(['OkCancelActions',
		 							'DirectionActions',
		 							'ColorActions',
		 							'MovieSelectionActions',
		 							'HelpActions'], {'ok': self.ok,
		 							'cancel': self.exit,
		 							'down': self.down,
		 							'up': self.up,
		 							'right': self.rightDown,
		 							'left': self.leftUp,
		 							'red': self.red,
		 							'yellow': self.yellow,
		 							'green': self.green,
		 							'blue': self.hideScreen,
		 							'showEventInfo': self.showHelp}, -1)
		self.onLayoutFinish.append(self.onLayoutFinished)

	def onLayoutFinished(self):
		self['headline'].setText("lade und verarbeite aktuelle Beiträge...")
		callInThread(self.threadDownloadPage, "%sactivity.php" % BASEURL, self.localhtml, self.makeMenu)

	def makeMenu(self, string):
		output = open(self.localhtml, 'rb').read()
		output = ensure_str(output.decode('latin1').encode('utf-8'))
		startpos = output.find('<div class="blockbody">')
		endpos = output.find('<ul id="footer_links"')
		bereich = unescape(output[startpos:endpos])
		posts = split(r'<div class="avatar">', bereich, flags=S)
		users = []
		logos = []
		links = []
		themen = []
		foren = []
		descs = []
		dates = []
		stats = []
		for post in posts:
			user = self.cleanupUserTags(self.searchOneValue(r'<a href=".*?">(.*?)</a>', post, None))
			if not user or "ForumBot" in user:
				continue
			users.append(user)
			logos.append(self.searchOneValue(r'<img src="(.*?)" alt="Avatar von', post, "%simages/styles/TheBeaconLight/misc/unknown.gif" % BASEURL))
			links.append(self.searchOneValue(r'<div class="fulllink"><a href="(.*?)">Weiterlesen</a></div>', post, None))
			quellen = self.searchTwoValues(r'das Thema.*?">(.*?)</a>\s*im Forum.*?">(.*?)</a>', post, "{kein Thema}", "{kein Forum}")
			themen.append(quellen[0])
			foren.append(quellen[1])
			desc = self.searchOneValue(r'<div class="excerpt">(.*?)</div>', post, "{keine Beschreibung}", flag_S=S)
			descs.append(sub("\n+\s*\n+", "", desc.replace("<br />", "").replace("\n", "")).strip())
			date = self.searchTwoValues(r'<span class="date">(.*?)<span class="time">(.*?)</span></span>', post, "{kein Datum}", "{keine Uhrzeit}")
			dates.append("%s%s" % (date[0], date[1]))
			stat = self.searchOneValue(r'<div class="views">(.*?) Antwort', post, "0")
			stats.append("%s%s" % (stat, " Antwort(en)") if int(stat) > 0 else "neues Thema erstellt")
		userlist = ", ".join([*set(users)])
		userlist = "%s…" % userlist[:200] if len(userlist) > 200 else userlist
		self['headline'].setText("lade fehlende Avatare...")
		self.downloadMissingAvatars(logos)
		self['headline'].setText("aktuelle Beiträge")
		for i, user in enumerate(users):
			res = ['']
			res.append(MultiContentEntryText(pos=(0, 0), size=(1800, 135), font=-1, backcolor=1381651, backcolor_sel=1381651, flags=RT_HALIGN_LEFT, text=''))
			res.append(MultiContentEntryPixmapAlphaTest(pos=(0, 0), size=(1800, 7), png=loadPNG(join(PLUGINPATH, "pic/line.png"))))
			realname = glob(join(AVATARPATH, "%s%s" % (logos[i][logos[i].rfind("/") + 1:logos[i].rfind(".")], ".*")))
			if realname:
				res.append(MultiContentEntryPixmapAlphaTest(pos=(7, 15), size=(108, 108), backcolor=1381651, backcolor_sel=1381651, png=LoadPixmap(realname[0]), flags=BT_SCALE | BT_KEEP_ASPECT_RATIO))
			res.append(MultiContentEntryText(pos=(135, 7), size=(1290, 405), font=-1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_LEFT, text=themen[i]))
			res.append(MultiContentEntryText(pos=(135, 51), size=(1290, 90), font=0, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_LEFT | RT_WRAP, text=descs[i]))
			res.append(MultiContentEntryText(pos=(1440, 7), size=(315, 40), font=1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_RIGHT, text=dates[i]))
			res.append(MultiContentEntryText(pos=(1440, 45), size=(315, 45), font=-1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_RIGHT, text=user))
			res.append(MultiContentEntryText(pos=(1440, 90), size=(315, 40), font=1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_RIGHT, text=stats[i]))
			self.menuentries.append(res)
			self.menulink.append("%s%s" % (BASEURL, links[i]))
			self.titellist.append(themen[i])
		res = ['']
		res.append(MultiContentEntryText(pos=(0, 0), size=(1800, 135), font=-1, backcolor=1381651, backcolor_sel=1381651, flags=RT_HALIGN_LEFT, text=''))
		res.append(MultiContentEntryPixmapAlphaTest(pos=(0, 0), size=(1800, 7), png=loadPNG(join(PLUGINPATH, "pic/line.png"))))
		res.append(MultiContentEntryPixmapAlphaTest(pos=(5, 10), size=(108, 108), backcolor=1381651, backcolor_sel=1381651, png=LoadPixmap(join(PLUGINPATH, "pic/user_stat.png")), flags=BT_SCALE | BT_KEEP_ASPECT_RATIO))
		res.append(MultiContentEntryText(pos=(135, 12), size=(1290, 40), font=-1, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_LEFT, text='beteiligte Benutzer'))
		res.append(MultiContentEntryText(pos=(135, 57), size=(1620, 86), font=0, backcolor=1381651, color=16777215, backcolor_sel=1381651, color_sel=2130055, flags=RT_HALIGN_LEFT | RT_WRAP, text=userlist))
		res.append(MultiContentEntryPixmapAlphaTest(pos=(89, 0), size=(1800, 7), png=loadPNG(join(PLUGINPATH, "pic/line.png"))))
		self.menuentries.append(res)
		self.menulink.append(None)
		self.titellist.append('beteiligte Benutzer')
		self['menu'].l.setList(self.menuentries)
		self['menu'].l.setItemHeight(135)
		self['menu'].moveToIndex(0)
		self['menu'].show()
		self.ready = True

	def ok(self):
		if self.ready is True:
			c = self.getIndex(self['menu'])
			link = self.menulink[c]
			if link is not None:
				self.session.openWithCallback(self.returnMenu, openATVThread, link, False, False)

	def green(self):
		if self.ready is True:
			self.menuentries = []
			self.menulink = []
			self.titellist = []
			callInThread(self.threadDownloadPage, "%sactivity.php" % BASEURL, self.localhtml, self.makeMenu)

	def yellow(self):
		if self.ready is True:
			self.session.open(openATVFav)

	def red(self):
		if self.ready is True:
			c = self['menu'].getSelectedIndex()
			name = self.titellist[c]
			self.session.openWithCallback(self.red_return, MessageBox, "\nForum\n'%s'\nzu den Favoriten hinzufügen?" % name, MessageBox.TYPE_YESNO)

	def red_return(self, answer):
		if answer is True:
			c = self['menu'].getSelectedIndex()
			favoriten = join(PLUGINPATH, "db/favoriten")
			if fileExists(favoriten):
				f = open(favoriten, 'a')
				data = "Forum: %s:::%s" % (self.titellist[c], self.menulink[c])
				f.write(data)
				f.write(linesep)
				f.close()
			self.session.open(openATVFav)
		else:
			self.session.open(openATVFav)

	def showHelp(self):
		if self.showhelp is False:
			self.showhelp = True
			self.toogleHelp.show()
		else:
			self.showhelp = False
			self.toogleHelp.hide()

	def returnMenu(self):
		pass

	def getIndex(self, list):
		return list.getSelectedIndex()

	def down(self):
		self['menu'].down()

	def up(self):
		self['menu'].up()

	def rightDown(self):
		self['menu'].pageDown()

	def leftUp(self):
		self['menu'].pageUp()

	def exit(self):
		if self.hideflag is False:
			f = open('/proc/stb/video/alpha', 'w')
			f.write('%i' % config.av.osd_alpha.value)
			f.close()
		if self.showhelp is True:
			self.showhelp = False
			self.toogleHelp.hide()
		else:
			self.session.deleteDialog(self.toogleHelp)
			if fileExists(self.localhtml):
				remove(self.localhtml)
			if fileExists(self.localhtml2):
				remove(self.localhtml2)
			if fileExists(self.picfile):
				remove(self.picfile)
			self.close()


def main(session, **kwargs):
	session.open(openATVMain)


def Plugins(**kwargs):
	return [PluginDescriptor(name='OpenATV Reader', description='opena.tv', where=[PluginDescriptor.WHERE_PLUGINMENU], icon='plugin.png', fnc=main), PluginDescriptor(name='OpenATV Reader', description='opena.tv', where=[PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main)]
