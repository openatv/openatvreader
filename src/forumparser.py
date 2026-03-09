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
from bs4 import BeautifulSoup
from getopt import getopt, GetoptError
from json import dump
from re import compile
from requests import get, exceptions
from sys import exit, argv
MODULE_NAME = __name__.split(".")[-1]


class FParserGlobals:
	MODULE_NAME = __name__.split(".")[-1]
	BASEURL = "https://www.opena.tv"


atvpglobals = FParserGlobals()


class FparserHelper:
	def getHTMLdata(self, url, timeout=(3.05, 6)):
		errMsg, htmlData = "", ""
		try:
			response = get(url, timeout=timeout)
			response.raise_for_status()
			errMsg, htmlData = "", response.text
			del response
			return errMsg, htmlData
		except exceptions.RequestException as errMsg:
			errMsg = str(errMsg).replace(atvpglobals.BASEURL.replace("https://", ""), "").replace("'", "").replace("/", "")
			print(f"[{MODULE_NAME}] ERROR in module 'getHTMLdata': {errMsg}")
			return errMsg, htmlData

	def createThreadUrl(self, threadId, startPage=0):
		return f"{atvpglobals.BASEURL}/viewtopic.php?t={threadId}&start={startPage}" if threadId else ""

	def createPostUrl(self, postId):
		return f"{atvpglobals.BASEURL}/viewtopic.php?p={postId}#p{postId}" if postId else ""

	def parseLatest(self, startPage=0):
		def setPostKey(key, value, replacements=[]):
			if value:
				text = value if isinstance(value, str) else value.get_text()
				if text:
					for replacement in replacements:
						text = text.replace(replacement, "")
					latestDict[key] = text

		latestList, latestUser = [], []
		url = f"{atvpglobals.BASEURL}/index.php?recent_topics_start={startPage}"
		errMsg, htmlData = fparser.getHTMLdata(url)
		if errMsg:
			return errMsg, {}
		pageList, pageUser = [], []
		try:
			xml = BeautifulSoup(htmlData, features="lxml")  # .replace('&amp;', '&')  # work around BeautifulSoup bug
		except Exception as errMsg:
			print(f"[{MODULE_NAME}] ERROR in module 'parseLatest': {errMsg}")
		threadTitle = "aktuelle Themen"
		currPost = startPage
		topicList = xml.find("ul", {"class": "topiclist topics collapsible"})
		for post in topicList.find_all("dl"):
			latestDict = {}
			topicTitle = post.find("a", class_="topictitle")
			setPostKey("title", topicTitle)
			url = topicTitle.get("href", "")
			setPostKey("threadId", url[url.find("?t=") + 3:url.rfind("&sid=")])
			respShow = post.find("div", class_="responsive-show")
			userName = respShow.get_text(strip=True)[19:]  # "Letzter Beitrag von  Testomat  « 23 Okt 2025 16:26"
			userName = userName[:userName.find("«")]
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
		if errMsg:
			return errMsg, {}
		try:
			xml = BeautifulSoup(htmlData, features="lxml")  # .replace('&amp;', '&')  # work around BeautifulSoup bug
		except Exception as errMsg:
			print(f"[{MODULE_NAME}] ERROR in module 'parseThread': {errMsg}")
		titleLine = xml.title.string.replace(" - openATV Forum", "")  # "LCD4linux - Seite 150"
		foundpos = titleLine.rfind("Seite")
		threadTitle = titleLine[:foundpos - 3] if foundpos != -1 else titleLine
		threadId = xml.find("input", {"name": "t", "type": "hidden"}).get("value")
		pages = xml.find("a", {"class": "button button-icon-only dropdown-trigger"}).get_text().strip("Seite ").split(" von ")
		currPage, maxPages = (convert2int(pages[0], 1), convert2int(pages[1], 1)) if pages and len(pages) > 1 else (1, 1)
		threadList, threadUser = [], []
		for post in xml.find_all("div", {"class": compile("post has-profile bg(.*?)")}):
			threadDict = {}
			setThreadKey("postId", post.get("id", "").strip("profile"))
			postProfile = post.find("dl", {"class": "postprofile"})
			if postProfile:
				userName = postProfile.find("a", {"class": compile("username(.*?)")}) or postProfile.find("span", {"class": compile("username(.*?)")})
				userName = userName.get_text()
				if userName not in threadUser:
					threadUser.append(userName)
				setThreadKey("userName", userName)
				avatar = postProfile.find("img", {"class": "avatar"})
				if avatar:
					avatarUrl = avatar.get("src", "").strip(".")
					setThreadKey("avatarUrl", f"{atvpglobals.BASEURL.rstrip('/')}{avatarUrl}" if avatarUrl else None)
				profilePosts = postProfile.find_all("dd", {"profile-posts"})
				setThreadKey("postsCounter", profilePosts[0].get_text() if len(profilePosts) > 0 else "")
			setThreadKey("online", "online" if "online" in post.get("class") else "")
			postBody = post.find("div", {"class": "postbody"})
			setThreadKey("postNumber", postBody.find("p", {"class": "author post-number post-number-phpbb post-number-bold"}), replacements=["\n"])
			setThreadKey("postTime", postBody.find("time").get_text())
			setThreadKey("shortContent", postBody.find("div", {"class": "content"}).get_text(separator=" ", strip=True)[:300])  # limit content as preview
			threadList.append(threadDict)
		return errMsg, {
			"threadTitle": threadTitle, "threadId": threadId,
			"currPage": currPage, "maxPages": maxPages,
			"posts": threadList, "user": list(set(threadUser))
			}

	def checkServerStatus(self):
		atvpglobals.BASEURL = bytes.fromhex("687474703A2F2F7265616465722E6F70656E612E7476E"[:-1]).decode()
		errMsg, htmlData = self.getHTMLdata(f"{atvpglobals.BASEURL}/index.php")
		return errMsg

	def parsePost(self, postId=""):
		def setPostKey(key, value, replacements=[]):
			if value:
				text = value if isinstance(value, str) else value.get_text()
				if text:
					for replacement in replacements:
						text = text.replace(replacement, "")
					postDict[key] = text

		if postId:
			url = f"{atvpglobals.BASEURL}/viewtopic.php?p={postId}#p{postId}"
		else:
			errMsg = "Neither threadId nor postId given."
			print(f"[{MODULE_NAME}] ERROR in module 'parseThread': {errMsg}")
			return errMsg, []
		errMsg, htmlData = fparser.getHTMLdata(url)
		if errMsg:
			return errMsg, []
		try:
			xml = BeautifulSoup(htmlData, features="lxml")  # .replace('&amp;', '&')  # work around BeautifulSoup bug
		except Exception as errMsg:
			print(f"[{MODULE_NAME}] ERROR in module 'parseThread': {errMsg}")
		for post in xml.find_all("div", class_=compile("post has-profile (.*?)")):
			pId = post.get("id", "").strip("profile")
			if postId != pId:
				continue
			postDict = {}
			setPostKey("postId", pId)
			postProfile = post.find("dl", {"class": "postprofile"})
			if postProfile:
				setPostKey("userName", postProfile.find("a", {"class": compile("username(.*?)")}))
				avatar = postProfile.find("img", {"class": "avatar"})
				if avatar:
					avatarUrl = avatar.get("src", "").strip(".")
					setPostKey("avatarUrl", f"{atvpglobals.BASEURL.rstrip('/')}{avatarUrl}" if avatarUrl else None)
				profileRank = postProfile.find("dd", {"class": "profile-rank"})
				if profileRank:
					rankUrl = profileRank.img.get("src", "").strip(".")
					setPostKey("userTitle", profileRank.img.get("title", ""))
					setPostKey("userRank", f"{atvpglobals.BASEURL.rstrip('/')}{rankUrl}" if rankUrl else None)
				setPostKey("registered", postProfile.find("dd", {"class": "profile-joined"}).get_text()[:-6])
				location = postProfile.find("dd", {"class": "profile-custom-field profile-phpbb_location"})
				if location:
					setPostKey("residence", location.get_text())
				receivers = postProfile.find_all("dd", {"class": compile("profile-custom-field profile-receiver_.*?")})
				receiverList = []
				for receiver in receivers:
					receiverList.append(receiver.get_text())
				if receiverList:
					postDict["receivers"] = receiverList
				profilePosts = postProfile.find_all("dd", {"profile-posts"})
				setPostKey("postsCounter", profilePosts[0].get_text() if len(profilePosts) > 0 else "")
				setPostKey("thxGiven", profilePosts[1].get_text() if len(profilePosts) > 1 else "")
				setPostKey("thxReceived", profilePosts[2].get_text() if len(profilePosts) > 2 else "")
			postBody = post.find("div", {"class": "postbody"})
			if postBody:
				setPostKey("postNumber", postBody.find("p", {"class": "author post-number post-number-phpbb post-number-bold"}), replacements=["\n"])
				setPostKey("online", "online" if postBody.find("div", {"class": compile("post .*? online")}) else "")
				setPostKey("postTime", postBody.find("time").get_text())
			fullContent = postBody.find("div", {"class": "content"}).get_text()
			while "\n\n\n" in fullContent:  # remove multiple '\n\
				fullContent = fullContent.replace("\n\n\n", "\n\n")
			setPostKey("fullContent", fullContent)
			changeLine = postBody.find("div", {"class": "notice"})
			if changeLine:
				setPostKey("changeLine", changeLine.get_text().strip())
		return errMsg, postDict


fparser = FparserHelper()


def main(argv):  # shell interface
	filename = ""
	resultDict = {}
	helpstring = "forumparser v1.0: try 'python forumparser.py -h' for more information"
	try:
		opts, args = getopt(argv, "j:l:t:p:h", ["json=", "latest=", "thread=", "post=", "help"])
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
					threadUrl = f"{atvpglobals.BASEURL}/viewtopic.php?t={threadId}&start={(int(pageNo) - 1) * 20}"
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
