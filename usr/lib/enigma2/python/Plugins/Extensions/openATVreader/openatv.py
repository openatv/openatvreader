#!/usr/bin/env python
# -*- coding: utf-8 -*-

# openATV Forums Reader
# maintainer: lolly - lolly.enigma2@gmail.com

#This plugin for enigma2 settop boxes is free software which entitles you to modify the source code,
#if you clearly identify the original license and developers, but you are not expressly authorized,
#to distribute this software / publish without source code. This applies for the original version,
#but also the version with your changes. That said, you also have the source code of your changes
#distribute / publish to.

### Import my_ globals Modules ###
import my_globals
reload(my_globals)
from my_globals import *
from __init__ import _

### Set Config Variables for the Plugin ###
config.openatv = ConfigSubsection()
config.openatv.version = NoSave(ConfigText(default="070"))
config.openatv.versiontext = NoSave(ConfigText(default="openATV Community Reader v0.7"))
config.openatv.autoupdate = ConfigYesNo(False)
config.openatv.username = ConfigText(default="VXNlcg==", fixed_size=False)
config.openatv.password = ConfigPassword(default="UGFzcw==", fixed_size=False)
config.openatv.directlogin = ConfigYesNo(False)

### Set Skin Config Variables for the Plugin ###
skins = []
for skin in os.listdir(my_globals.pluginPath+my_globals.skinsPath):
	if os.path.isdir(os.path.join(my_globals.pluginPath+my_globals.skinsPath, skin)):
		skins.append(skin)
config.openatv.skin = ConfigSelection(default = defaultskin, choices = skins)

### Build Cookie Function ###
ck = {}

class OPENA_TV_HauptScreen(MyScreen):
	def __init__(self, session):
		### Lock the Bouquet Buttons from Mmy_screen.py ###
		self.Noswitch = True
		self.session = session
		### init automatic the correct skin .xml  ###
		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_HauptScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_HauptScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()
		### init the Screen ###
		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"menu":self.keySetup,
			"showMovies":self.keyHelp,
			"red":self.keyCancel,
			"green":self.keyWatchlist,
			"yellow":self.keyAdd,
			"blue":self.keyLogin,
			"1":self.keyChangelog,
			"2":self.keyBuglist
			}, -1)

		### Lock the Buttons if Screen loading ###
		self.keyLocked = True
		### init Skin Parts ###
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Please wait..."))
		self['text_login'] = Label ()
		self['infopanel'] = Label ()
		self['text_ico_menu'] = Label ()
		self['text_ico_help'] = Label ()
		self['text_ico_key1'] = Label ()
		self['text_ico_key2'] = Label ()
		self['text_ico_red'] = Label ()
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self['feedstatus'] = Label ()
		self['feedstatus_gruen'] = Label ()
		self['feedstatus_gelb'] = Label ()
		self['feedstatus_rot'] = Label ()
		self['avatar'] = Pixmap()
		### Set List functions ###
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		if config.openatv.autoupdate.value:
			self.updatetest()

		username = base64.b64decode(config.openatv.username.value)
		self.username = username.decode("utf-8").encode("iso-8859-1")
		self.username = decodeHtml(self.username)

		self.password = base64.b64decode(config.openatv.password.value)
		password = self.password.decode("utf-8").encode("iso-8859-1")
		self.password_md5 = md5.md5(password).hexdigest()

		self.onFirstExecBegin.append(self.loadData)

	def loadData(self):
		if self.username == "User" and self.password == "Pass":
			self.loginOK = False
			self.stoken = ''
			### Use the Plugin as guest without Login and more functions ###
			getPage(open_url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)
		else:
			getPage(check_url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.checkLogin).addErrback(self.dataError)

	def checkLogin(self, data):
		# not correct working at the moment. Comes in the Future if needed
		if 'class="welcomelink"' in str(data):
			self['text_header'].setText(_("You´re login session is active as, %s")%self.username)
			self.loginOK = True
			secutoken = re.findall('var SECURITYTOKEN = "(.*?)"', data, re.S)
			if secutoken:
				self.stoken = secutoken[0]
			getPage(open_url, method="GET", headers={'Content-Type': 'application/x-www-form-urlencoded'},
			followRedirect=True, timeout=30, cookies=ck).addCallback(self.parseData).addErrback(self.dataError)
		else:
			self.loginOK = False
			self.stoken = ''
			getPage(open_url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)

	def login(self):
		if self.keyLocked:
			return
		self['text_header'].setText(_("Try to Login as %s")%self.username)
		loginData = {'vb_login_username':self.username, 'vb_login_password':self.password, 'do':'login'}
		getPage(login_url, method='POST',
			postdata=urlencode(loginData), cookies=ck,
			headers={'Content-Type':'application/x-www-form-urlencoded','User-agent': 'Mozilla/4.0',}).addCallback(self.Refresh).addErrback(self.dataError)

	def Refresh(self, data):
		if "Danke" in str(data):
			self['text_header'].setText(_("Thanks for login, %s")%self.username)
			self.loginOK = True
			c_user = '1'
			loginData = {'vb_login_username': self.username,
						 's': '',
						 'securitytoken': 'guest',
						 'do': 'login',
						 'vb_login_md5password': self.password_md5,
						 'vb_login_md5password_utf': self.password_md5,
						 'cookieuser' : c_user
						 }
			getPage(login_url, method="POST",
				postdata=urlencode(loginData), headers={'Content-Type': 'application/x-www-form-urlencoded'},
				followRedirect=True, timeout=30, cookies=ck).addCallback(self.loginDone).addErrback(self.dataError)
		else:
			self.loginOK = False
			self['text_header'].setText(_("Login failed!"))
			self['text_login'].setText(_("Login failed!"))

	def loginDone(self, data):
		### if you have a 15 min. Timeban, can you not login
		### please wait 15 min. without login try
		if 'Bitte warte 15 Minuten, bevor du eine erneute Anmeldung versuchst.</b>' in data:
			self['text_header'].setText(_("You must use Guest Mode!"))
			self['text_login'].setText(_("You are 15 Min. Timebanned"))
		else:
			self['text_header'].setText(_("You are logged in as %s! Please wait a Moment!")%self.username)
		getPage(open_url, method="GET", headers={'Content-Type': 'application/x-www-form-urlencoded'},
			followRedirect=True, timeout=30, cookies=ck).addCallback(self.parseData).addErrback(self.dataError)

		secutoken = re.findall('var SECURITYTOKEN = "(.*?)"', data, re.S)
		if secutoken:
			self.stoken = secutoken[0]

	def parseData(self, data):
		self.liste = []
		if self.loginOK == True:
			self['text_ico_blue'].setText("")
			parse = re.findall('src=".*?/statusicon_blue/(.*?)".*?<h2\sclass="forumtitle"><a\shref="(.*?)">(.*?)<.*?forumstats.*?<li>(.*?)<.*?<li>(.*?)<.*?lastpostlabel">(.*?)<.*?title=".*?">(.*?)<.*?title="(.*?)">.*?lastpostdate">(.*?)<span\sclass="time">(.*?)<', data, re.S)
			for (pic,url,title,threads,posts,last,lastthread,lastuser,l_date,l_time) in parse:
				lastuser = lastuser.replace(' ist gerade online','').replace(' ist offline','')
				lastpost = "Von "+lastuser+' - '+l_date+', '+l_time
				title = title.replace("E2World - YouTube Channel","Marktplatz")
				url = url.replace("https://www.youtube.com/channel/UC95hFgcA4hzKcOQHiEFX3UA","http://www.opena.tv/forum31/")
				self.liste.append(((decodeHtml(title), url, pic, decodeHtml(threads), decodeHtml(posts),decodeHtml(last),decodeHtml(lastthread),decodeHtml(lastpost))))
			self.liste.insert(0, (_("Football Betgame"), "http://www.opena.tv/vbsoccer.php", '', '', '', '', '', ''))
			self.liste.insert(0, (_("What is new?"), "http://www.opena.tv/activity.php", '', '', '', '', '', ''))
			self.liste.insert(0, ("openATV Git", "https://github.com/openatv", '', '', '', '', '', ''))
			self.liste.insert(0, (_("Read PM"), "http://www.opena.tv/private.php", '', '', '', '', '', ''))
			self.ml.setList(map(self.forenlist, self.liste))
			self['text_header'].setText(_("openATV Foren"))
			step2 = re.findall('<div id="contentMain">(.*?)Top 10 Statistik', data, re.S)
			step3 = re.findall('<h2 class="blockhead" align="center">(.*?)<a.*?src=".*?".*?id="dbtech_infopanel.*?src="(.*?)".*?<td width="50%".*?>(.*)Neue', step2[0], re.S)
			for (greeting,avatar,infopanel) in step3:
				avatar = open_url+avatar
				infopanel = cleanHtml(infopanel)
				infopanel = infopanel.strip()
				CoverHelper(self['avatar']).getCover(avatar)
				self['infopanel'].setText("%s\n\n\n%s" % (decodeHtml(greeting),decodeHtml(infopanel)))
		else:
			self.liste = []
			parse = re.findall('src=".*?/statusicon_blue/(.*?)".*?<h2\sclass="forumtitle"><a\shref="(.*?)[\?].*?">(.*?)<.*?forumstats.*?<li>(.*?)<.*?<li>(.*?)<.*?lastpostlabel">(.*?)<.*?title=".*?">(.*?)<.*?title="(.*?)">.*?lastpostdate">(.*?)<span\sclass="time">(.*?)<', data, re.S)
			for (pic,url,title,threads,posts,last,lastthread,lastuser,l_date,l_time) in parse:
				lastuser = lastuser.replace(' ist gerade online','').replace(' ist offline','')
				lastpost = "Von "+lastuser+' - '+l_date+', '+l_time
				title = title.replace("E2World - YouTube Channel","Marktplatz")
				url = url.replace("https://www.youtube.com/channel/UC95hFgcA4hzKcOQHiEFX3UA","http://www.opena.tv/forum31/")
				self.liste.append(((decodeHtml(title), url, pic, decodeHtml(threads), decodeHtml(posts),decodeHtml(last),decodeHtml(lastthread),decodeHtml(lastpost))))
			self.liste.insert(0, (_("What is new?"), "http://www.opena.tv/activity.php", '', '', '', '', '', ''))
			self.liste.insert(0, ("openATV Git", "https://github.com/openatv", '', '', '', '', '', ''))
			self.ml.setList(map(self.forenlist, self.liste))
			self['text_header'].setText(_("openATV Foren"))
			self['infopanel'].setText(_("Welcome Guest please login, for full functions!"))
			if self.username == "User" and self.password == "Pass":
				self['text_ico_blue'].setText(_(" "))
			else:
				self['text_ico_blue'].setText(_("Login"))
			CoverHelper(self['avatar']).getCover("/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/no_avatar.png")
		urlfeed = "http://ampel.mynonpublic.com/Ampel/index.php?noreload"
		datafeed = urllib.urlopen(urlfeed).read()
		if re.match(".*?gruen.png", datafeed, re.S):
			self['feedstatus_gruen'].setText(" Sicher")
		else:
			if re.match(".*?gelb.png", datafeed, re.S):
				self['feedstatus_gelb'].setText(" Bedenklich")
		 	else:
				self['feedstatus_rot'].setText(" Kritisch")
		self['text_ico_menu'].setText(_(" = Setup"))
		self['text_ico_help'].setText(_(" = About"))
		self['text_ico_key1'].setText(_(" = Changelog"))
		self['text_ico_key2'].setText(_(" = Worklist"))
		self['text_ico_red'].setText(_("Exit"))
		self['text_ico_green'].setText(_("Load Favorites"))
		self['text_ico_yellow'].setText(_("Add to Favorites"))
		self['feedstatus'].setText(_("Feedstatus: "))
		self.keyLocked = False

	def updatetest(self):
		getPage("http://lollys-plugins.de/feeds/openatv_c_reader/version.txt", timeout=15).addCallback(self.gotUpdateInfo).addErrback(self.updatefeedError)

	def gotUpdateInfo(self, html):
		self.html = html
		tmp_infolines = html.splitlines()
		remoteversion = tmp_infolines[0]
		self.updateurl = tmp_infolines[1]
		if config.openatv.version.value < remoteversion:
			self.session.openWithCallback(self.startUpdate, MessageBox, (_("An update is available for openATV Community Reader Plugin! Do you want to download and install now?")), MessageBox.TYPE_YESNO)

	def updatefeedError(self, error=""):
		self.session.open(MessageBox, (_("Update Check failed! Host not responding")), MessageBox.TYPE_INFO, timeout=3)

	def startUpdate(self, answer):
		if answer is True:
			self.session.open(OPENA_TV_Update,self.updateurl)

	def updatefeedError(self, error=""):
		self.session.open(MessageBox, (_("Update Feed not available!")), MessageBox.TYPE_INFO, timeout=3)

	def keyWatchlist(self):
		if self.keyLocked:
			return
		if self.loginOK == True:
			login = "X"
		else:
			login = ""
		self.session.open(OPENA_TV_Favorites, self.stoken, login)

	def keySetup(self):
		if self.keyLocked:
			return
		self.session.open(OPENA_TV_Setup)

	def keyHelp(self):
		if self.keyLocked:
			return
		self.session.open(OPENA_TV_About)

	def keyLogin(self):
		if self.keyLocked:
			return
		if self.username == "User" and self.password == "Pass":
			return
		self.login()

	def keyChangelog(self):
		self.session.open(openATV_Changelog)

	def keyBuglist(self):
		self.session.open(openATV_Buglist)

	def ok(self):
		if self.keyLocked:
			return
		name = self['liste'].getCurrent()[0][0]
		url = self['liste'].getCurrent()[0][1]
		if self.loginOK == True:
			login = "X"
		else:
			login = ""
		if name == "Was ist neu?" or name == "What is new?":
			self.session.open(OPENA_TV_WhatsNew, url, name, self.stoken, login)
		elif name == "Fussball Tippspiele" or name == "Football Betgame":
			self.session.open(OPENA_TV_Tippspiel, url, name, self.stoken)
		elif name == "Private Nachrichten" or name == "Read PM":
			self.session.open(OPENA_TV_PM_Overview, url, name, self.stoken)
		elif name == "openATV Git":
			self.session.open(OPENA_TV_GIT, url, name)
		else:
			self.session.open(OPENA_TV_Threads, url, name, self.stoken, login)

	def keyCancel(self):
		if self.keyLocked:
			return
		self.keyLocked = True
		if self.loginOK == True:
			self.session.open(MessageBox, (_("please wait a moment for logout!")), MessageBox.TYPE_INFO, timeout=5)
			getPage(open_url, method="GET", headers={'Content-Type': 'application/x-www-form-urlencoded'},
			followRedirect=True, timeout=30, cookies=ck).addCallback(self.getLogoutHash).addErrback(self.dataError)
		else:
			self.close()

	def getLogoutHash(self, data):
		if re.match('.*?do=logout&amp;logouthash', data, re.S):
			steplogout = re.findall('do=logout&amp;logouthash=(.*?)"', data, re.S)
			self.logout_url = "http://www.opena.tv/login.php?do=logout&logouthash=%s"%(steplogout[0])
			getPage(self.logout_url, timeout=15).addCallback(self.refresh_logout).addErrback(self.dataError)

	def refresh_logout(self, data):
		if re.match('.*?erfolgreich vom Forum abgemeldet', data, re.S):
			self.session.open(MessageBox, (_("successful logged out! plugin shutdown!")), MessageBox.TYPE_INFO, timeout=5)
			self.keyLocked = False
			self.close()
		else:
			self.session.open(MessageBox, (_("error by the log out")), MessageBox.TYPE_INFO, timeout=3)
			self.keyLocked = False
			self.close()

	def keyAdd(self):
		if self.keyLocked:
			return
		name = self['liste'].getCurrent()[0][0]
		url = self['liste'].getCurrent()[0][1]
		if url == "http://www.opena.tv/vbsoccer.php" \
		or url == "http://www.opena.tv/activity.php" \
		or url == "https://github.com/openatv" \
		or url == "http://www.opena.tv/private.php":
			message = self.session.open(MessageBox, (_("Entry not addable to favorites list")), MessageBox.TYPE_INFO, timeout=3)
		else:
			fn = "/etc/enigma2/oATv_favorites"
			if not fileExists(fn):
				open(fn,"w").close()
			try:
				writePlaylist = open(fn, "a")
				writePlaylist.write('"Forum:" "%s" "%s"\n' % (name, url))
				writePlaylist.close()
				message = self.session.open(MessageBox, (_("Forum was added to the favorite list.")), MessageBox.TYPE_INFO, timeout=3)
			except:
				pass

class openATV_Changelog(MyScreen):
	def __init__(self, session):
		self.Noswitch = True
		self.deLog = True
		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_Changelog.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_Changelog.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()
		self.session = session
		MyScreen.__init__(self, session)

		self["myActionMap"] = ActionMap(["My_Actions"], {
			"ok": self.cancel,
			"cancel": self.cancel,
			"left": self.keyLeft,
			"right": self.keyRight,
			"down": self.keyDown,
			"up": self.keyUp,
			"red": self.loadPage,
			"nextBouquet" : self.keyTxtPageUp,
			"prevBouquet" : self.keyTxtPageDown
		}, -1)

		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Please wait..."))
		self['text_ico_red'] = Label (_(" "))
		self['text'] = ScrollLabel("")
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.keyLocked = True
		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		url = "http://lollys-plugins.de/quickinfo-openatv-community-reader/"
		if self.deLog == True:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getlog_de).addErrback(self.dataError)
		else:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getlog_en).addErrback(self.dataError)

	def getlog_de(self, data):
		self.liste = []
		self['text_header'].setText(_("Changelog German"))
		self['text_ico_red'].setText(_(" Changelog in Englisch"))
		first = re.findall('Changelog Deutsch(.*?)class="spdiv">', data, re.S)
		parse = re.findall('<p>(.*?):<br>(.*?)</p>', first[0], re.S)
		for (title,log) in parse:
			log = decodeHtml(log)
			self.liste.append(((decodeHtml(title), cleanLexi(log))))
		self.ml.setList(map(self.listleft, self.liste))
		self.keyLocked = False
		self.deLog = False
		self.showInfos()

	def getlog_en(self, data):
		if self.deLog == True:
			self.getlog_de()
		else:
			self.liste = []
			self['text_header'].setText(_("Changelog Englisch"))
			self['text_ico_red'].setText(_(" Changelog in German"))
			first = re.findall('Changelog Englisch(.*?)class="spdiv">', data, re.S)
			parse = re.findall('<p>(.*?):<br>(.*?)</p>', first[0], re.S)
			for (title,log) in parse:
				log = decodeHtml(log)
				self.liste.append(((decodeHtml(title), cleanLexi(log))))
			self.ml.setList(map(self.listleft, self.liste))
			self.keyLocked = False
			self.deLog = True
			self.showInfos()

	def showInfos(self):
		log = self['liste'].getCurrent()[0][1]
		log = log.replace('<br>','\n')
		self['text'].setText(decodeHtml(log))

	def ok(self):
		self.close()

	def cancel(self):
		self.close(None)

class openATV_Buglist(MyScreen):
	def __init__(self, session):
		self.Noswitch = True
		self.deLog = True
		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_Changelog.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_Changelog.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()
		self.session = session
		MyScreen.__init__(self, session)

		self["myActionMap"] = ActionMap(["My_Actions"], {
			"ok": self.cancel,
			"cancel": self.cancel,
			"left": self.keyLeft,
			"right": self.keyRight,
			"down": self.keyDown,
			"up": self.keyUp,
			"red": self.loadPage,
			"nextBouquet" : self.keyTxtPageUp,
			"prevBouquet" : self.keyTxtPageDown
		}, -1)

		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Please wait..."))
		self['text_ico_red'] = Label (_(" "))
		self['text'] = ScrollLabel("")
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.keyLocked = True
		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		url = "http://lollys-plugins.de/quickinfo-openatv-community-reader/"
		if self.deLog == True:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getlog_de).addErrback(self.dataError)
		else:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getlog_en).addErrback(self.dataError)

	def getlog_de(self, data):
		self.liste = []
		self['text_header'].setText(_("Worklist German"))
		self['text_ico_red'].setText(_(" Worklist in Englisch"))
		first = re.findall('Worklist: Deutsch(.*?)class="spdiv">', data, re.S)
		parse = re.findall('oATV-(.*?):<br>(.*?)</p>', first[0], re.S)
		for (title,log) in parse:
			log = decodeHtml(log)
			self.liste.append(((decodeHtml(title), cleanLexi(log))))
		self.ml.setList(map(self.listleft, self.liste))
		self.keyLocked = False
		self.deLog = False
		self.showInfos()

	def getlog_en(self, data):
		if self.deLog == True:
			self.getlog_de()
		else:
			self.liste = []
			self['text_header'].setText(_("Worklist Englisch"))
			self['text_ico_red'].setText(_(" Worklist in German"))
			first = re.findall('Worklist: Englisch(.*?)class="spdiv">', data, re.S)
			parse = re.findall('oATV-(.*?):<br>(.*?)</p>', first[0], re.S)
			for (title,log) in parse:
				log = decodeHtml(log)
				self.liste.append(((decodeHtml(title), cleanLexi(log))))
			self.ml.setList(map(self.listleft, self.liste))
			self.keyLocked = False
			self.deLog = True
			self.showInfos()

	def showInfos(self):
		log = self['liste'].getCurrent()[0][1]
		log = log.replace('<br>','\n')
		self['text'].setText(decodeHtml(log))

	def ok(self):
		self.close()

	def cancel(self):
		self.close(None)
		
class OPENA_TV_About(MyScreen):
	def __init__(self, session):
		self.Noswitch = True
		self.session = session
		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_About.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_About.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.keyCancel,
			"cancel": self.keyCancel,
			}, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Developer: lolly\nWebseite: http://lollys-plugins.de"))
		self['text1'] = Label (_("Do you like the plugin?"))
		self['text2'] = Label (_("Do you want to make a donation for the development?"))
		self['text3'] = Label (_("Then send me a donation via PayPal!"))
		self['pp'] = Label (_("Donate by PayPal:"))
		self['pp1'] = Label (_("1. Log in to PayPal."))
		self['pp2'] = Label (_("2. Click: send money."))
		self['pp3'] = Label (_("3. Send money to friends and family."))
		self['pp4'] = Label (_("4. E-Mail Address: lolly.enigma2@gmail.com"))
		self['pp5'] = Label (_("5. Amount: free choice."))
		self['pp6'] = Label (_("6. send money."))
		self['pp7'] = Label (_("I thank you for the support!"))
		self['text_info'] = Label (_("You can not use PayPal? Then send me an e-mail to lolly.enigma2@gmail.com"))
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		if self.keyLocked:
			return

	def ok(self):
		if self.keyLocked:
			return

class OPENA_TV_Favorites(MyScreen):
	def __init__(self, session, stoken, login):
		self.Noswitch = True
		self.stoken = stoken
		self.login = login
		if self.login == "X":
			self.login = True
		else:
			self.login == False
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_Watchlist.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_Watchlist.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"red": self.keyDel, }, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s Favorites")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Favorites"))
		self['text_ico_red'] = Label (_("Delete"))
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self.firstpage = 1
		self.page = 1
		self.lastpage = 0
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self.liste = []
		if fileExists("/etc/enigma2/oATv_favorites"):
			readentrys = open("/etc/enigma2/oATv_favorites","r")
			for rawData in readentrys.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				if data:
					(what, title, url) = data[0]
					self.liste.append((what,title,url))
			self.liste.sort()
			self.ml.setList(map(self.favolist, self.liste))
			readentrys.close()
			self.showInfos()
			self.keyLocked = False

	def showInfos(self):
		exist = self['liste'].getCurrent()
		if self.keyLocked or exist == None:
			return
		title = self['liste'].getCurrent()[0][1]
		if not re.match('.*?----------------------------------------', title):
			self['text_header'].setText(title)
		else:
			self['text_header'].setText('')

	def ok(self):
		exist = self['liste'].getCurrent()
		if self.keyLocked or exist == None:
			return
		name = self['liste'].getCurrent()[0][1]
		url = self['liste'].getCurrent()[0][2]
		what = self['liste'].getCurrent()[0][0]
		if self.login == True:
			login = "X"
		else:
			login = ""
		if what == "Forum:":
			self.session.open(OPENA_TV_Threads, url, name, self.stoken, login)
		else:
			self.session.open(OPENA_TV_ThreadContent, url, name, self.stoken, login)

	def keyDel(self):
		exist = self['liste'].getCurrent()
		if self.keyLocked or exist == None:
			return
		selectedName = self['liste'].getCurrent()[0][2]
		writeTmp = open("/etc/enigma2/oATv_favorites.tmp","w")
		if fileExists("/etc/enigma2/oATv_favorites"):
			readStations = open("/etc/enigma2/oATv_favorites","r")
			for rawData in readStations.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				if data:
					(what, title, url ) = data[0]
					if url != selectedName:
						writeTmp.write('"%s" "%s" "%s"\n' % (what, title, url))
			readStations.close()
			writeTmp.close()
			shutil.move("/etc/enigma2/oATv_favorites.tmp", "/etc/enigma2/oATv_favorites")
			self.loadPage()

class OPENA_TV_Update(Screen):
	def __init__(self, session, updateurl):
		self.session = session
		self.updateurl = updateurl
		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_Update.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_Update.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()
		Screen.__init__(self, session)

		self["log"] = ScrollLabel()
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Update"))
		self.keyLocked = True
		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		ul = self["log"]
		ul.instance.setZPosition(1)
		self["log"].setText(_("Starting openATV Community Reader update, please wait..."))
		self.startPluginUpdate()

	def startPluginUpdate(self):
		self.container=eConsoleAppContainer()
		self.container.appClosed.append(self.finishedPluginUpdate)
		self.container.stdoutAvail.append(self.log)
		self.container.execute("opkg update ; opkg install --force-overwrite --force-depends " + str(self.updateurl))

	def finishedPluginUpdate(self,retval):
		self.container.kill()
		self.session.openWithCallback(self.restartGUI, MessageBox, (_("openATV Community Reader successfully updated!\nDo you want to restart the Enigma2 GUI now?")), MessageBox.TYPE_YESNO)
		self.keyLocked = False

	def restartGUI(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 3)
		else:
			self.close()

	def log(self,str):
		self["log"].setText(str)

class OPENA_TV_Setup(Screen, ConfigListScreen):
	def __init__(self, session):
		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_Setup.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_Setup.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()
		Screen.__init__(self, session)
		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = session, on_change = self.changedEntry)
		self.setTitle(_("openATV Reader - Setup"))

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.save,
			"cancel": self.keyCancel,
			"red": self.keyCancel,
			"green": self.save }, -1)

		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Setup"))
		self['text_ico_red'] = Label(_("Exit"))
		self['text_ico_green'] = Label(_("Save"))
		self.setup_title = _("openATV Reader - Setup")
		self.onLayoutFinish.append(self.load_list)

	def load_list(self):
		self.list = []
		self.list.append(getConfigListEntry(_("Username:"), config.openatv.username))
		self.list.append(getConfigListEntry(_("Password:"), config.openatv.password))
		self.list.append(getConfigListEntry(_("Automatic Update Check:"), config.openatv.autoupdate))
		self.list.append(getConfigListEntry(_("Skin:"), config.openatv.skin))
		self["config"].setList(self.list)

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.load_list()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.load_list()

	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def createSummary(self):
		return SetupSummary

	def save(self):
		config.openatv.autoupdate.setValue(config.openatv.autoupdate.value)
		config.openatv.autoupdate.save()
		config.openatv.skin.setValue(config.openatv.skin.value)
		config.openatv.skin.save()
		config.openatv.username.setValue(config.openatv.username.value)
		config.openatv.username.value = base64.b64encode(config.openatv.username.value)
		config.openatv.username.save()
		config.openatv.password.setValue(config.openatv.password.value)
		config.openatv.password.value = base64.b64encode(config.openatv.password.value)
		config.openatv.password.save()
		configfile.save()
		self.session.open(MessageBox,(_("Setup Settings Saved! Please restart the Plugin!")),MessageBox.TYPE_INFO, timeout = 3)
		self.close()

class OPENA_TV_WhatsNew(MyScreen):
	def __init__(self, session, url, name, stoken, login):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.stoken = stoken
		self.login = login
		if self.login == "X":
			self.login = True
		else:
			self.login == False
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_DefaultScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_DefaultScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel}, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Please wait..."))
		self['thread_title'] = Label (_("Threads"))
		self['last_post'] = Label ()
		self['text_ico_red'] = Label ()
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self['text_ico_menu'] = Label ()
		self['text_ico_help'] = Label ()
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self.liste = []
		url = self.url
		if self.login == True:
			postData = {'securitytoken': self.stoken}
			getPage(url, method="POST", postdata=urlencode(postData), cookies=ck,
				headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
				followRedirect=True, timeout=30).addCallback(self.parseData).addErrback(self.dataError)
		else:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		print "We are now parsing"
		step1 = re.findall('class="date">(.*?)&nbsp;<span class="time">(.*?)</span></span>.*?href="members.*?">(.*?)</a>(.*?)<a href="(.*?).html.*?">(.*?)</a>(.*?)<a href=".*?">(.*?)</a>(.*?).', data, re.S)
		for (date,time,user,t1,url,t2,t3,t4,t5) in step1:
			print date,time,user,t1,url,t2,t3,t4,t5
			title = date+time+'    '+user+' '+t1+' '+t2+' '+t3+' '+t4+' '+t5
			self.liste.append((decodeHtml(title),url,t1,t2))
		self.ml.setList(map(self.listleft, self.liste))
		self['text_header'].setText(_("What is new?"))
		self.keyLocked = False

	def ok(self):
		if self.keyLocked:
			return
		if self.login == True:
			login = "X"
		else:
			login = ""
		name = self['liste'].getCurrent()[0][3]
		url = open_url+self['liste'].getCurrent()[0][1]
		self.session.open(OPENA_TV_ThreadContent, url, name, self.stoken, login)

class OPENA_TV_Threads(MyScreen):
	def __init__(self, session, url, name, stoken, login):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.stoken = stoken
		self.login = login
		if self.login == "X":
			self.login = True
		else:
			self.login == False
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_DefaultScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_DefaultScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"up" : self.keyUp,
			"down" : self.keyDown,
			"right" : self.keyRight,
			"left" : self.keyLeft,
			"red": self.keyAdd,
			"green": self.keyPageNumber,
			"yellow": self.switchToFirst,
			"blue": self.switchToLast,
			"nextBouquet" : self.keyPageUp,
			"prevBouquet" : self.keyPageDown,
			"showMovies":self.SubForum }, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label ("Please wait...")
		self['thread_title'] = Label (_("Threads"))
		self['last_post'] = Label (_(" "))
		self['text_ico_red'] = Label (_("Add to Favorites"))
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self['text_ico_menu'] = Label ()
		self['text_ico_help'] = Label ()
		self.firstpage = 1
		self.page = 1
		self.lastpage = 0
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self.liste = []
		url = self.url + "index" +str(self.page)+".html"
		if self.login == True:
			postData = {'securitytoken': self.stoken}
			getPage(url, method="POST", postdata=urlencode(postData), cookies=ck,
				headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
				followRedirect=True, timeout=30).addCallback(self.parseData).addErrback(self.dataError)
		else:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		if re.match('.*?Unterforen: <span class="forumtitle">', data, re.S):
			self['text_ico_help'].setText(_("Load Sub Forums"))
		step1 = re.findall('rel="nofollow">Forum-Optionen</a>(.*?)class="optionlabel">Bereiche</li>', data, re.S)
		if self.login == True:
			step2 = re.findall('<li class="threadbit(.*?)"\sid="thread.*?class="(.*?)">.*?class=".*?threadtitle.*?" href="(.*?).html".*?>(.*?)</a>.*?class="threadstats.*?<li>(.*?)</li>.*?<li>(.*?)</li>.*?title="(.*?)">.*?<dd>(.*?)<span class="time">(.*?)</span>', step1[0], re.S)
			for (threadstatus,rating,url,title,ant,hits,l_user,l_date,l_time) in step2:
				l_user = l_user.replace(' ist offline','').replace(' ist gerade online','')
				title = decodeHtml(title)
				ant = cleanHtml(ant)
				hits = cleanHtml(hits)
				l_user = cleanHtml(l_user)
				threadstatus = threadstatus.strip()
				if threadstatus == "moved":
					l_user = "Moved"
					l_date = "Moved"
					l_time = ""
				self.liste.append((decodeHtml(title),url,threadstatus,rating,decodeHtml(ant),decodeHtml(hits),l_user,l_date,l_time))
		else:
			step2 = re.findall('class="title" href="(.*?).html.*?".*?>(.*?)</a>.*?class="username.*?title="(.*?)".*?Antworten:.*?>(.*?)</a>.*?Hits:(.*?)</li>.*?<strong>(.*?)</strong>.*?<dd>(.*?)<span class="time">(.*?)</span>', step1[0], re.S)
			for (url,title,creator,ant,hits,l_user,l_post,l_time) in step2:
				l_user = l_user.replace(' ist offline','').replace(' ist gerade online','')
				title = decodeHtml(title)
				ant = "Antworten: "+ant
				ant = cleanHtml(ant)
				hits = "Hits: "+hits
				hits = cleanHtml(hits)
				l_user = cleanHtml(l_user)
				self.liste.append((decodeHtml(title),url, decodeHtml(creator),'',decodeHtml(ant),decodeHtml(hits),l_user,l_post,l_time))
		self.ml.setList(map(self.threadlist, self.liste))
		self.keyLocked = False
		if re.match('.*?class="popupctrl">Seite.*?von\s.*?</a>', data, re.S):
			lastpage = re.findall('class="popupctrl">Seite.*?von\s(.*?)</a>', data)
			self.lastpage = int(lastpage[0])
			self['page'].setText("Seite: %s / %s" % (str(self.page), str(self.lastpage)))
			self['text_ico_green'].setText(_("Go to Site..."))
			self['text_ico_yellow'].setText(_("Switch to First Site"))
			self['text_ico_blue'].setText(_("Switch to Last Site"))
			self.showInfos()
		else:
			self.showInfos()

	def showInfos(self):
		name = self['liste'].getCurrent()[0][0]
		self['text_header'].setText(_("%s: %s")%(self.name,name))

	def SubForum(self):
		if self.keyLocked:
			return
		if self.login == True:
			login = "X"
		else:
			login = ""
		if len(self.liste) == 0:
			name = "Subforum"
		else:
			name = self['liste'].getCurrent()[0][0]
		self.session.open(OPENA_TV_In_SubForums, self.url, name, self.stoken, login)

	def keyAdd(self):
		if self.keyLocked:
			return
		name = self['liste'].getCurrent()[0][0]
		url = self['liste'].getCurrent()[0][1]
		fn = "/etc/enigma2/oATv_favorites"
		if not fileExists(fn):
			open(fn,"w").close()
		try:
			writePlaylist = open(fn, "a")
			writePlaylist.write('"Thread:" "%s" "%s"\n' % (name, url))
			writePlaylist.close()
			message = self.session.open(MessageBox, (_("Thread was added to the favorite list.")), MessageBox.TYPE_INFO, timeout=3)
		except:
			pass

	def ok(self):
		if self.keyLocked:
			return
		if self.login == True:
			login = "X"
		else:
			login = ""
		name = self['liste'].getCurrent()[0][0]
		url = self['liste'].getCurrent()[0][1]
		self.session.open(OPENA_TV_ThreadContent, url, name, self.stoken, login)

class OPENA_TV_In_SubForums(MyScreen):
	def __init__(self, session, url, name, stoken, login):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.stoken = stoken
		self.login = login
		if self.login == "X":
			self.login = True
		else:
			self.login = False
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_DefaultScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_DefaultScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"red": self.keyAdd,
			"nextBouquet" : self.keyPageUp,
			"prevBouquet" : self.keyPageDown }, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label ("Please wait...")
		self['thread_title'] = Label (_("Sub-Forum"))
		self['last_post'] = Label ()
		self['text_ico_red'] = Label (_("Add to Favorites"))
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self['text_ico_menu'] = Label ()
		self['text_ico_help'] = Label ()
		self.firstpage = 1
		self.page = 1
		self.lastpage = 0
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self.liste = []
		url = self.url + "index" +str(self.page)+".html"
		if self.login == True:
			postData = {'securitytoken': self.stoken}
			getPage(url, method="POST", postdata=urlencode(postData), cookies=ck,
				headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
				followRedirect=True, timeout=30).addCallback(self.parseData).addErrback(self.dataError)
		else:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		parse = re.findall('statusicon_blue/(.*?)".*?forumtitle.*?href="(.*?)">(.*?)<.*?forumstats.*?<li>(.*?)<.*?<li>(.*?)<', data, re.S)
		for (pic,url,title,threads,posts) in parse:
			self.liste.append(((decodeHtml(title), url, pic, decodeHtml(threads), decodeHtml(posts),'','','','','')))
		self.ml.setList(map(self.subforenlist, self.liste))
		self['text_header'].setText("Sub-Forums")
		self.keyLocked = False

	def keyAdd(self):
		if self.keyLocked:
			return
		name = self['liste'].getCurrent()[0][0]
		url = self['liste'].getCurrent()[0][1]
		fn = "/etc/enigma2/oATv_favorites"
		if not fileExists(fn):
			open(fn,"w").close()
		try:
			writePlaylist = open(fn, "a")
			writePlaylist.write('"Thread:" "%s" "%s"\n' % (name, url))
			writePlaylist.close()
			message = self.session.open(MessageBox, (_("Forum was added to the favorite list.")), MessageBox.TYPE_INFO, timeout=3)
		except:
			pass

	def ok(self):
		if self.keyLocked:
			return
		name = self['liste'].getCurrent()[0][0]
		url = self['liste'].getCurrent()[0][1]
		if self.login == True:
			login = "X"
		else:
			login = ""
		self.session.open(OPENA_TV_Threads, url, name, self.stoken, login)

class OPENA_TV_ThreadContent(MyScreen):
	def __init__(self, session, url, name, stoken, login):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.stoken = stoken
		self.login = login
		if self.login == "X":
			self.login = True
		else:
			self.login == False
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_Thread.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_Thread.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"up" : self.keyUp,
			"down" : self.keyDown,
			"right" : self.keyTxtPageDown,
			"left" : self.keyTxtPageUp,
			"red": self.keyFullText,
			"green": self.keyPageNumber,
			"yellow": self.switchToFirst,
			"blue": self.switchToLast,
			"nextBouquet" : self.keyPageUp,
			"prevBouquet" : self.keyPageDown }, -1)

		self.keyLocked = False
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Please wait..."))
		self['text'] = ScrollLabel()
		self['text_ico_red'] = Label (_("Full Text"))
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self.firstpage = 1
		self.page = 1
		self.lastpage = 1
		self.liste = []
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self.liste = []
		url = self.url + '-' +str(self.page) + '.html'
		if self.login == True:
			postData = {'securitytoken': self.stoken}
			getPage(url, method="POST", postdata=urlencode(postData), cookies=ck,
				headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
				followRedirect=True, timeout=30).addCallback(self.parseData).addErrback(self.dataError)
		else:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
#		if self.login == True:
		parse = re.findall('class="postdate old">.*?class="date">(.*?)&nbsp;<span class="time">(.*?)</span></span>.*?id="postcount.*?name="(.*?)"></a>.*?class="userinfo">(.*?)class="postbody">.*?postcontent restore ">(.*?)</blockquote>', data, re.S)
		for (date,time,post,user,content) in parse:
			if re.match('.*?class="username.*?href=".*?title=".*?">.*?class="usertitle"', user, re.S):
				username = re.findall('class="username.*?href=".*?title="(.*?)">', user, re.S)
				usertitle = re.findall('class="usertitle">(.*?)</span>', user, re.S)
				user = decodeHtml(username[0])
				usertitle = usertitle[0]
			else:
				user = "Gast"
				usertitle = "N/A"
			user = user.replace(' ist offline','').replace(' ist gerade online','')
			usertitle = usertitle.replace('<!--','').replace('-->','')
			content = content.replace('<img src="http://www.opena.tv/images/styles/TheBeaconDark/misc/quote_icon.png" alt="Zitat" />','').replace('<div class="message">','')
			content = decodeHtml(content)
			content = content = cleanHtml(content)
			self.liste.append((date,time,post,user,decodeHtml(usertitle.strip()),decodeHtml(content.strip())))
		self.ml.setList(map(self.thread_Contentlist, self.liste))
		if re.match('.*?class="popupctrl">Seite.*?von\s.*?</a>', data, re.S):
			lastpage = re.findall('class="popupctrl">Seite.*?von\s(.*?)</a>', data)
			self.lastpage = int(lastpage[0])
			self['page'].setText("Seite: %s / %s" % (str(self.page), str(self.lastpage)))
			self['text_ico_green'].setText(_("Go to Site..."))
			self['text_ico_yellow'].setText(_("Switch to First Site"))
			self['text_ico_blue'].setText(_("Switch to Last Site"))
			self.showInfos()
		else:
			self.showInfos()
		self.keyLocked = False

	def showInfos(self):
		date = self['liste'].getCurrent()[0][0]
		time = self['liste'].getCurrent()[0][1]
		post = self['liste'].getCurrent()[0][2]
		user = self['liste'].getCurrent()[0][3]
		usertitle = self['liste'].getCurrent()[0][4]
		content = self['liste'].getCurrent()[0][5]
		self['text_header'].setText(_("Thread: %s")%self.name)
		self['text'].setText(_("Post: %s\nUser: %s\n%s\n%s %s\n\n%s")%(post,user,usertitle,date,time,content))

	def keyFullText(self):
		date = self['liste'].getCurrent()[0][0]
		time = self['liste'].getCurrent()[0][1]
		post = self['liste'].getCurrent()[0][2]
		user = self['liste'].getCurrent()[0][3]
		usertitle = self['liste'].getCurrent()[0][4]
		content = self['liste'].getCurrent()[0][5]
		self.session.open(OPENA_TV_ThreadFull, post,user,usertitle,date,time,content, self.name)

	def ok(self):
		return

class OPENA_TV_ThreadFull(MyScreen):
	def __init__(self, session, post,user,usertitle,date,time,content, name):
		self.post = post
		self.user = user
		self.usertitle = usertitle
		self.date = date
		self.time = time
		self.content = content
		self.name = name
		self.Noswitch = False
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_FullScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_FullScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"up" : self.keyTxtPageUp,
			"down" : self.keyTxtPageDown,
			"right" : self.keyTxtPageDown,
			"left" : self.keyTxtPageUp }, -1)

		self.keyLocked = False
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Full Post: %s")%self.name)
		self['text'] = ScrollLabel()
		self.liste = []
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self['text'].setText(_("Post: %s\nUser: %s\n%s\n%s %s\n\n%s")%(self.post,self.user,self.usertitle,self.date,self.time,self.content))

	def ok(self):
		return

class OPENA_TV_PM_Overview(MyScreen):
	def __init__(self, session, url, name, stoken):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.stoken = stoken
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_DefaultScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_DefaultScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel
			}, -1)
		username = base64.b64decode(config.openatv.username.value)
		self.username = decodeHtml(username)
		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Welcome %s in your PM Case")%self.username)
		self['thread_title'] = Label (_("Private Messages"))
		self['last_post'] = Label ()
		self['text_ico_red'] = Label ()
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self['text_ico_menu'] = Label ()
		self['text_ico_help'] = Label ()
		self.liste = []
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		postData = {'securitytoken': self.stoken}
		getPage(self.url, method="POST", postdata=urlencode(postData), cookies=ck,
			headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
			followRedirect=True, timeout=30).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		get_pm = re.findall('<div class="datetime">.*?">(.*?)<span class="time">(.*?)</span>.*?statusicon_blue/(.*?)".*?pmid=(.*?)" class="title">(.*?)</a>.*?username understate">(.*?)</a>', data, re.S)
		for (date,time,pic,pmid,title,user) in get_pm:
			fromuser = (_("From: %s")%user)
			self.liste.append((decodeHtml(title),date,time,pic,pmid,fromuser,user))
		self.ml.setList(map(self.listPM, self.liste))
		self.keyLocked = False

	def ok(self):
		if self.keyLocked:
			return
		title = self['liste'].getCurrent()[0][0]
		pmid = self['liste'].getCurrent()[0][4]
		user = self['liste'].getCurrent()[0][6]
		self.session.open(OPENA_TV_ReadPM, title, pmid, user, self.stoken)

class OPENA_TV_ReadPM(MyScreen):
	def __init__(self, session, title, pmid, user, stoken):
		self.title = title
		self.pmid = pmid
		self.user = user
		self.stoken = stoken
		self.Noswitch = False
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_FullScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_FullScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"up" : self.keyTxtPageUp,
			"down" : self.keyTxtPageDown,
			"right" : self.keyTxtPageDown,
			"left" : self.keyTxtPageUp }, -1)

		self.keyLocked = False
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Read PM from: %s")%self.user)
		self['text'] = ScrollLabel()
		self.liste = []
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		url = open_url+"private.php?do=showpm&pmid="+self.pmid
		postData = {'securitytoken': self.stoken}
		getPage(url, method="POST", postdata=urlencode(postData), cookies=ck,
			headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
			followRedirect=True, timeout=30).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		get_date = re.findall('<span class="date">(.*?)<span class="time">(.*?)</span></span>', data, re.S)
		for (date, time) in get_date:
			get_date = decodeHtml(date)+ ' '+time
		get_pm_content = re.findall('<div class="postbody">.*?<h2.*?>(.*?)</h2>.*?postcontent restore ">(.*?)</blockquote>', data, re.S)
		for (title,content) in get_pm_content:
			content = cleanHtml(content)
			self['text'].setText(_("%s\n%s\n\n%s")%(get_date,decodeHtml(title.strip()),decodeHtml(content.strip())))

	def ok(self):
		return

class OPENA_TV_GIT(MyScreen):
	def __init__(self, session, url, name):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_DefaultScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_DefaultScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel}, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("openATV Git"))
		self['thread_title'] = Label (_("Repositorys"))
		self['last_post'] = Label ()
		self['text_ico_red'] = Label ()
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self['text_ico_menu'] = Label ()
		self['text_ico_help'] = Label ()
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self.liste = []
		url = self.url
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		step1 = re.findall('class="repo-list-name">.*?href="(.*?)".*?>(.*?)</a>.*?datetime="(.*?)T(.*?)Z"', data, re.S)
		for (url,title,date,time) in step1:
			title = title.strip()
			update = 'Updated: '+date+' '+time
			self.liste.append((title,update,url))
		self.ml.setList(map(self.listgit, self.liste))
		self.keyLocked = False

	def ok(self):
		if self.keyLocked:
			return
		name = self['liste'].getCurrent()[0][0]
		url = git_url+self['liste'].getCurrent()[0][2]
		self.session.open(OPENA_TV_Commits, url, name)

class OPENA_TV_Commits(MyScreen):
	def __init__(self, session, url, name):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_DefaultScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_DefaultScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"nextBouquet" : self.keyPageUp,
			"prevBouquet" : self.keyPageDown
			}, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("openATV Git"))
		self['thread_title'] = Label (_("%s Commits")%self.name)
		self['last_post'] = Label ()
		self['text_ico_red'] = Label ()
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self['text_ico_menu'] = Label ()
		self['text_ico_help'] = Label ()
		self.page = 1
		self.lastpage = 0
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self.liste = []
		url = self.url + '/commits/master?page=' + str(self.page)
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		step1 = re.findall('class="commit-title ">.*?href="(.*?)".*?title=".*?">(.*?)</a>.*?relative-time">(.*?)</time>', data, re.S)
		for (url,title,updated) in step1:
			update = 'Updated '+updated
			self.liste.append((title,update,url))
		self.ml.setList(map(self.listgit, self.liste))
		self['page'].setText("Seite: %s " % str(self.page))
		self.keyLocked = False

	def ok(self):
#		if self.keyLocked:
		return
	
class OPENA_TV_Tippspiel(MyScreen):
	def __init__(self, session, url, name, stoken):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.stoken = stoken
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_DefaultScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_DefaultScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel
			}, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("%s")%self.name)
		self['thread_title'] = Label (_("League"))
		self['last_post'] = Label ()
		self['text_ico_red'] = Label ()
		self['text_ico_green'] = Label ()
		self['text_ico_yellow'] = Label ()
		self['text_ico_blue'] = Label ()
		self['text_ico_menu'] = Label ()
		self['text_ico_help'] = Label ()
		self.liste = []
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		postData = {'securitytoken': self.stoken}
		getPage(self.url, method="POST", postdata=urlencode(postData), cookies=ck,
			headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
			followRedirect=True, timeout=30).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		parse = re.findall('class="blocksubhead">Deutschland</h3>(.*?)class="blocksubhead">Sonstiges</h3>', data, re.S)
		getleague = re.findall('<li.*?href="vbsoccer.*?l=(.*?)">(.*?)</a>', parse[0], re.S)
		for (url,title) in getleague:
			self.liste.append((decodeHtml(title),url))
		self.ml.setList(map(self.listleft, self.liste))
		self.keyLocked = False

	def ok(self):
		if self.keyLocked:
			return
		name = self['liste'].getCurrent()[0][0]
		rankinglist = self['liste'].getCurrent()[0][1]
		url = build_league_url+'ranking&l='+rankinglist
		self.session.open(OPENA_TV_Tippspiel_UserRanking, url, name, self.stoken)

class OPENA_TV_Tippspiel_UserRanking(MyScreen):
	def __init__(self, session, url, name, stoken):
		self.Noswitch = False
		self.url = url
		self.name = name
		self.stoken = stoken
		self.session = session

		self.skin_path = my_globals.pluginPath+my_globals.skinsPath
		path = "%s/%s/OPENA_TV_DefaultScreen.xml" % (self.skin_path, config.openatv.skin.value)
		if not fileExists(path):
			path = self.skin_path + my_globals.skinFallback + "/OPENA_TV_DefaultScreen.xml"
		with open(path, "r") as f:
			self.skin = f.read()
			f.close()

		MyScreen.__init__(self, session)

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel
			}, -1)

		self.keyLocked = True
		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("User Ranking %s")%self.name)
#		self['thread_title'] = Label (_("Liga"))
		self["platz"] = Label(_("Pl."))
		self["name"] = Label(_("Name"))
		self["gewer"] = Label(_("Counted"))
		self["zero"] = Label(_("0 Pkt."))
		self["one"] = Label(_("1 Pkt."))
		self["two"] = Label(_("2 Pkt."))
		self["three"] = Label(_("3 Pkt."))
		self["diff"] = Label(_("+ -"))
		self["points"] = Label(_("Pkt."))
		self.ml = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['liste'] = self.ml

		self.onLayoutFinish.append(self.loadPage)

	def loadPage(self):
		self.liste = []
		postData = {'securitytoken': self.stoken}
		getPage(self.url, method="POST", postdata=urlencode(postData), cookies=ck,
			headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
			followRedirect=True, timeout=30).addCallback(self.parseData).addErrback(self.dataError)

	def parseData(self, data):
		parse = re.findall('vbsoccer-ranking-table(.*?)class="optionlabel"', data, re.S)
		get_user_ranking = re.findall('<tr>.*?rankpos">(.*?)<.*?"members.*?class=.*?>(.*?)<.*?valuated">(.*?)<.*?ptssys_count"><.*?>(.*?)<.*?ptssys_count"><.*?>(.*?)<.*?ptssys_count"><.*?>(.*?)<.*?ptssys_count"><.*?>(.*?)<.*?matchday_points">(.*?)<.*?sumpoints"><b>(.*?)<', parse[0], re.S)
		for (rank,name,gewertet,zero,one,two,three,diff,points) in get_user_ranking:
			self.liste.append((decodeHtml(rank),name,gewertet,zero,one,two,three,diff,points))
		self.ml.setList(map(self.ranglisten, self.liste))
		self.keyLocked = False

	def ok(self):
#		if self.keyLocked:
		return