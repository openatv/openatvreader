#######################################################################################################
#                                                                                                     #
#  forumparser is a parser for the OpenA.TV fourum homepage using BeatifulSoup (BS4) and              #
#  it is a multiplatform tool (runs on Enigma2 & Windows and probably many others)                    #
#  Coded by Mr.Servo @ openATV (c) 2025                                                               #
#  Learn more about the tool by running it in the shell: "python Buildstatus.py -h"                   #
#  ---------------------------------------------------------------------------------------------------#
#  This plugin is licensed under the GNU version 3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>.  #
#  This plugin is NOT free software. It is open source, you are allowed to modify it (if you keep     #
#  the license), but it may not be commercially distributed. Advertise with this tool is not allowed. #
#  For other uses, permission from the authors is necessary.                                          #
#                                                                                                     #
#######################################################################################################

# PYTHON IMPORTS
from bs4 import BeautifulSoup, Tag
from getopt import getopt, GetoptError
from json import dump
from re import compile
from requests import get, exceptions
from sys import exit, argv
MODULE_NAME = __name__.split(".")[-1]


class FParserGlobals:
	MODULE_NAME: str = __name__.split(".")[-1]
	BASEURL: str = "https://www.opena.tv"


fpglobals = FParserGlobals()


class FparserHelper:
	def getHTMLdata(self, url, timeout=(3.05, 6)):
		try:
			response = get(url, timeout=timeout)
			return None, response.text
		except exceptions.RequestException as errMsg:
			errMsg = str(errMsg).replace(fpglobals.BASEURL.replace("http://", ""), "").replace("host=,'", "")
			print(f"[{MODULE_NAME}] ERROR in module 'getHTMLdata': {errMsg}")
			return errMsg, None

	def getBinaryData(self, url, timeout=(3.05, 6)):
		try:
			response = get(url, timeout=timeout)
			return None, response.content
		except exceptions.RequestException as errMsg:
			errMsg = str(errMsg).replace(fpglobals.BASEURL.replace("http://", ""), "").replace("host=,'", "")
			print(f"[{MODULE_NAME}] ERROR in module 'getBinaryData': {errMsg}")
			return errMsg, None

	def createThreadUrl(self, threadId, startPage=0):
		return f"{fpglobals.BASEURL}/viewtopic.php?t={threadId}&start={startPage}" if threadId else ""

	def createPostUrl(self, postId):
		return f"{fpglobals.BASEURL}/viewtopic.php?p={postId}#p{postId}" if postId else ""

	def parseLatest(self, startPage=0):
		def setPostKey(key, value, replacements=[]):
			if value:
				text = value if isinstance(value, str) else value.get_text()
				if text:
					for replacement in replacements:
						text = text.replace(replacement, "")
					latestDict[key] = text

		latestList, latestUser = [], []
		url = f"{fpglobals.BASEURL}/index.php?recent_topics_start={startPage}"
		errMsg, htmlData = fparser.getHTMLdata(url)
		if errMsg or not htmlData:
			return errMsg, {}
		pageList, pageUser = [], []
		try:
			xml = BeautifulSoup(htmlData, features="lxml")  # .replace('&amp;', '&')  # work around BeautifulSoup bug
		except Exception as errMsg:
			errText = f"[{MODULE_NAME}] ERROR in module 'parseLatest': {errMsg}"
			print(errText)
			return errText, {}
		threadTitle = "aktuelle Themen"
		currPost = startPage
		topicList = xml.find("ul", {"class": "topiclist topics collapsible"})
		posts = topicList.find_all("dl") if isinstance(topicList, Tag) else []
		for post in posts:
			if not isinstance(post, Tag):
				continue
			latestDict = {}
			topicTitle = post.find("a", class_="topictitle")
			if not isinstance(topicTitle, Tag):
				continue
			setPostKey("title", topicTitle)
			href = str(topicTitle.get("href", "") or "")
			tThreadPos = href.find("?t=")
			if tThreadPos == -1:
				continue
			sidPos = href.rfind("&sid=")
			threadId = href[tThreadPos + 3:sidPos if sidPos != -1 else len(href)]
			setPostKey("threadId", threadId)
			respShow = post.find("div", class_="responsive-show")
			if not isinstance(respShow, Tag):
				continue
			userName = respShow.get_text(strip=True)[19:]  # "Letzter Beitrag von Testomat  « 23 Okt 2025 16:26"
			separator = userName.find("«")
			userName = userName[:separator] if separator != -1 else userName
			setPostKey("userName", userName)
			setPostKey("latestLine", respShow, replacements=(["\t", "\n"]))
			setPostKey("sourceLine", post.find('div', class_="responsive-hide"), replacements=(["\t", "\n"]))
			setPostKey("views", post.find("dd", class_="views"))
			setPostKey("posts", post.find("dd", class_="posts"))
			if userName not in pageUser:
				pageUser.append(userName)
			pageList.append(latestDict)
		latestList += pageList
		latestUser += pageUser
		return errMsg, {"threadTitle": threadTitle, "currPost": currPost, "threads": latestList, "users": list(set(latestUser))}  # remove duplicates from userlist

	def parseThread(self, threadUrl=""):
		def setThreadKey(key, value, replacements=[]):
			if value:
				text = value if isinstance(value, str) else value.get_text()
				if text:
					for replacement in replacements:
						text = text.replace(replacement, "")
					threadDict[key] = text

		def convert2int(valueStr, fallbackInt=0):
			return int(valueStr) if valueStr.isdigit() else fallbackInt

		if not threadUrl:
			errMsg = "No threadUrl given."
			print(f"[{MODULE_NAME}] ERROR in module 'parseThread': {errMsg}")
			return errMsg, {}
		errMsg, htmlData = fparser.getHTMLdata(threadUrl)
		if errMsg or not htmlData:
			return errMsg, {}
		xml = None
		try:
			xml = BeautifulSoup(htmlData, features="lxml")  # .replace('&amp;', '&')  # work around BeautifulSoup bug
		except Exception as errMsg:
			print(f"[{MODULE_NAME}] ERROR in module 'parseThread': {errMsg}")
			return f"Failed to parse thread page: {errMsg}", {}
		if xml is None:
			print(f"[{MODULE_NAME}] ERROR in module 'parseThread': {errMsg}")
			return f"Failed to parse thread page: {errMsg}", {}
		titleLine = xml.title.string if xml.title else ""  # "LCD4linux - Seite 150"
		titleLine = titleLine.replace(" - openATV Forum", "") if titleLine else ""
		foundpos = titleLine.rfind("Seite")
		threadTitle = titleLine[:foundpos - 3] if foundpos != -1 else titleLine
		threadInput = xml.find("input", {"name": "t", "type": "hidden"})
		threadId = threadInput.get("value") if isinstance(threadInput, Tag) else None
		pagination = xml.find("div", {"class": "pagination"})  # <div class="pagination">   21 Beiträge   <ul>
		pagination = pagination.get_text().strip().split(" ")[0] if isinstance(pagination, Tag) else "1"
		maxPages = ((int(pagination) - 1) // 20) + 1 if pagination.isdigit() else 1
		active = xml.find("li", {"class": "active"})  # <li class="active"><span>11</span></li>
		active = active.get_text() if isinstance(active, Tag) else "1"
		currPage = int(active) if active.isdigit() else 1
		threadList, threadUser = [], []
		for post in xml.find_all("div", {"class": compile("post has-profile bg(.*?)")}):
			if not post or not isinstance(post, Tag):
				continue
			threadDict = {}
			postId = str(post.get("id") or "").strip("profile")
			setThreadKey("postId", postId)
			postProfile = post.find("dl", {"class": "postprofile"})
			if isinstance(postProfile, Tag):
				userName = postProfile.find("a", {"class": compile("username(.*?)")}) or postProfile.find("span", {"class": compile("username(.*?)")})
				if isinstance(userName, Tag):
					userName = userName.get_text()
					if userName not in threadUser:
						threadUser.append(userName)
					setThreadKey("userName", userName)
				avatar = postProfile.find("img", {"class": "avatar"})
				if isinstance(avatar, Tag):
					avatarUrl = str(avatar.get("src") or "").strip(".")
					setThreadKey("avatarUrl", f"{fpglobals.BASEURL}{avatarUrl}" if avatarUrl else "")
				profilePosts = postProfile.find_all("dd", class_="profile-posts")
				if profilePosts:
					setThreadKey("postsCounter", profilePosts[0].get_text())
			postClasses = post.get("class") or []
			if isinstance(postClasses, str):
				postClasses = [postClasses]
			setThreadKey("online", "online" if "online" in postClasses else "")
			postBody = post.find("div", {"class": "postbody"})
			if isinstance(postBody, Tag):
				postNumber = postBody.find("p", {"class": "author post-number post-number-phpbb post-number-bold"})
				setThreadKey("postNumber", postNumber, replacements=["\n"])
				timeEl = postBody.find("time")
				if isinstance(timeEl, Tag):
					setThreadKey("postTime", timeEl.get_text())
				contentEl = postBody.find("div", {"class": "content"})
				if isinstance(contentEl, Tag):
					setThreadKey("shortContent", contentEl.get_text(separator=" ", strip=True)[:300])  # limit content as preview
			threadList.append(threadDict)
		return errMsg, {
			"threadTitle": threadTitle, "threadId": threadId,
			"currPage": currPage, "maxPages": maxPages,
			"posts": threadList, "user": list(set(threadUser))
			}

	def checkServerStatus(self):
		fpglobals.BASEURL = bytes.fromhex("687474703A2F2F7265616465722E6F70656E612E7476E"[:-1]).decode()
		errMsg, _ = self.getHTMLdata(f"{fpglobals.BASEURL}/index.php")
		return errMsg

	def parsePost(self, postId=""):
		def setPostKey(key, value, replacements=[]):
			if value:
				text = value if isinstance(value, str) else value.get_text()
				if text:
					for replacement in replacements:
						text = text.replace(replacement, "")
					postDict[key] = text

		postDict = {}
		if postId:
			url = f"{fpglobals.BASEURL}/viewtopic.php?p={postId}#p{postId}"
		else:
			errMsg = "Neither threadId nor postId given."
			print(f"[{MODULE_NAME}] ERROR in module 'parseThread': {errMsg}")
			return errMsg, {}
		errMsg, htmlData = fparser.getHTMLdata(url)
		if errMsg or not htmlData:
			return errMsg, {}
		try:
			xml = BeautifulSoup(htmlData, features="lxml")  # .replace('&amp;', '&')  # work around BeautifulSoup bug
		except Exception as errMsg:
			print(f"[{MODULE_NAME}] ERROR in module 'parseThread': {errMsg}")
			return str(errMsg), {}
		for post in xml.find_all("div", class_=compile("post has-profile .*?")):
			if not isinstance(post, Tag):
				continue
			pId = str(post.get("id", "") or "").strip("profile")
			if postId != pId:
				continue
			postDict = {}
			setPostKey("postId", pId)
			postProfile = post.find("dl", {"class": "postprofile"})
			if isinstance(postProfile, Tag):
				userName = postProfile.find("a", {"class": compile("username(.*?)")})
				if isinstance(userName, Tag):
					setPostKey("userName", userName)
				setPostKey("online", "online" if "online" in str(post) else "")
				avatar = postProfile.find("img", {"class": "avatar"})
				if isinstance(avatar, Tag):
					avatarUrl = str(avatar.get("src", "") or "").strip(".")
					setPostKey("avatarUrl", f"{fpglobals.BASEURL}{avatarUrl}" if avatarUrl else "")
				profileRank = postProfile.find("dd", {"class": "profile-rank"})
				if isinstance(profileRank, Tag):
					rankImg = profileRank.find("img")
					if isinstance(rankImg, Tag):
						rankUrl = str(rankImg.get("src", "") or "").strip(".")
						setPostKey("userTitle", rankImg.get("title", ""))
						setPostKey("userRank", f"{fpglobals.BASEURL}{rankUrl}" if rankUrl else "")
				joined = postProfile.find("dd", {"class": "profile-joined"})
				if isinstance(joined, Tag):
					setPostKey("registered", joined.get_text()[:-6])
				location = postProfile.find("dd", {"class": "profile-custom-field profile-phpbb_location"})
				if isinstance(location, Tag):
					setPostKey("residence", location.get_text())
				receivers = postProfile.find_all("dd", {"class": compile("profile-custom-field profile-receiver_.*?")})
				receiverList = []
				for receiver in receivers:
					if isinstance(receiver, Tag):
						receiverList.append(receiver.get_text())
				if receiverList:
					postDict["receivers"] = receiverList
				profilePosts = postProfile.find_all("dd", class_="profile-posts")
				setPostKey("postsCounter", profilePosts[0].get_text() if len(profilePosts) > 0 else "")
				setPostKey("thxGiven", profilePosts[1].get_text() if len(profilePosts) > 1 else "")
				setPostKey("thxReceived", profilePosts[2].get_text() if len(profilePosts) > 2 else "")
			postBody = post.find("div", {"class": "postbody"})
			if isinstance(postBody, Tag):
				setPostKey("postNumber", postBody.find("p", {"class": "author post-number post-number-phpbb post-number-bold"}), replacements=["\n"])
				timeEl = postBody.find("time")
				if isinstance(timeEl, Tag):
					setPostKey("postTime", timeEl.get_text())
				contentEl = postBody.find("div", {"class": "content"})
				if isinstance(contentEl, Tag):
					fullContent = contentEl.get_text()
					while "\n\n\n" in fullContent:
						fullContent = fullContent.replace("\n\n\n", "\n\n")
					setPostKey("fullContent", fullContent)
				changeLine = postBody.find("div", {"class": "notice"})
				if isinstance(changeLine, Tag):
					setPostKey("changeLine", changeLine.get_text().strip())
		return errMsg, postDict


fparser = FparserHelper()


def main(argv):  # shell interface
	filename = ""
	resultDict = {}
	helpstring = "forumparser v1.0: try 'python forumparser.py -h' for more information"
	try:
		opts, _ = getopt(argv, "j:l:t:p:h", ["json=", "latest=", "thread=", "post=", "help"])
	except GetoptError as error:
		print(f"ERROR: {error}\n{helpstring}")
		exit(2)
	errMsg = fparser.checkServerStatus()
	if errMsg:
		print("ERROR:", errMsg)
		exit(2)
	for opt, arg in opts:
		opt = opt.lower().strip()
		arg = arg.strip()
		if not opts or opt == "-h":
			print("Usage 'forumparser v1.0': python forumparser.py [option...] <data>\n"
			"Example: python forumparser.py -l 1 -j lastest.json\n"
			"-l, --latest <pageNo>\t\tGet list of latest threads\n"
			"-t, --thread <threadId-pageNo>\tGet posts of a single thread (details: see code)\n"
			"-p, --post <postId>\t\tGet a single post (details: see code)\n"
			"-j, --json <filename>\t\tFile output formatted in JSON\n")
			exit()
		elif opt in ("-l", "--latest"):
			if arg != "0" and arg.isdigit():
				errMsg, resultDict = fparser.parseLatest((int(arg) - 1) * 5)
				if errMsg:
					print("ERROR:", errMsg)
			else:
					print(f"ERROR: Can't download page-no '{arg}'")
		elif opt in ("-j", "--json"):
			filename = arg
		elif opt in ("-t", "--thread"):
			arguments = arg.split("-")
			threadId, pageNo = arguments[0], arguments[1] if len(arguments) > 1 else "0"
			if pageNo != "0":
				if pageNo.isdigit():
					threadUrl = f"{fpglobals.BASEURL}/viewtopic.php?t={threadId}&start={(int(pageNo) - 1) * 20}"
					errMsg, resultDict = fparser.parseThread(threadUrl)
					if errMsg:
						print("ERROR:", errMsg)
						exit(2)
			else:
				print("ERROR: Can't download page-no '0'")
		elif opt in ("-p", "--post"):
			errMsg, resultDict = fparser.parsePost(arg)
			if errMsg:
				print("ERROR:", errMsg)
				exit(2)
	if resultDict and filename:
		with open(filename, "w") as file:
			dump(resultDict, file)
		print(f"JSON file '{filename}' was successfully created.")


if __name__ == "__main__":
	main(argv[1:])
