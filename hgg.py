#!/usr/bin/python3
# -*- coding: utf-8 -*-

#Copyright (c) 2015, Wong Cho Ching
#All rights reserved.
#
#Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
#1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
#2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#
#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#Development Dates: 24/12/14, 27/12/14~30/12/14, 03/01/14

#######################
###  CONFIGURATION  ###
#######################
TIME_FORMAT = '%y-%m-%d'
SHUFFLE_SEED = 9001 #The seed of randomizing the order of thumbnails. Not very useful
DATABASE_FLUST_INTERVAL = 60 #The interval of saving the database, in seconds
THUMBNAIL_SIZE = (256, 256)

#Depending on the packages you have installed, you may want to modify these lists
SHOW_UNSUPPORTED_FORMATS = True #If false, unsupported file format are hidden in the gallery
SUPPORTED_IMAGE_FORMATS = ['.jpg', '.png']
SUPPORTED_VIDEO_FORMATS = ['.avi', '.mov', '.mp4']
SUPPORTED_MUSIC_FORMATS = ['.wav', '.ogg', '.mp3']
SUPPORTED_MISC_FORMATS = [] #If SHOW_UNSUPPORTED_FORMATS is set to False, the formats listed here is still shown in the gallery
MEDIA_FORMATS = SUPPORTED_IMAGE_FORMATS+SUPPORTED_MUSIC_FORMATS+SUPPORTED_VIDEO_FORMATS
SUPPORTED_FORMATS = MEDIA_FORMATS+SUPPORTED_MISC_FORMATS
##############################
###  END OF CONFIGURATION  ###
##############################

import os, sys, hashlib, shutil, re, random, time, io, urllib.request
from PIL import Image
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
GObject.threads_init()
Gst.init(None)
Gst.CLOCK_TIME_NONE = 18446744073709551615 #Workaround of https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=753505

README_TEXT = '''This gallery is generated by HTML Gallery Generator(https://github.com/wongcc966422/HTMLGalleryGenerator)
==========
1. Put your photos, videos or whatever into ./assets
2. Run `hgg.py <this folder> <template>`
3a. The HTML files are generated in ./
3b. The thumbnails are generated in ./thumbnails
3c. The converted files are generated in ./converted, if this script is instructed to convert files by the template
3d. The database file ./database is created
4. To update the gallery, update the content in ./assets then run `hgg.py <this folder> <template>` again
==========
For the template, either use the one provided by default, or make a new one yourself. Please refer to the README file of the project
You may want to put css and js files into ./ for your webpage files. All webpage files are placed in ./ . Therefore, it is easy to make HTML reference to other files(e.g. css, js)
'''

BLOCK_ELEMENTS = ['for', 'if']

####################
###Util functions###
####################

def mkdirIfNotExist(d):
	if not os.path.exists(d):
		os.mkdir(d)

def createIfNotExist(f):
	if not os.path.exists(f):
		open(f, 'a').close()

#Stolen from https://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size/1094933#1094933
def humanReadable(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

#Get all files in the directory recursively. Stolen from https://stackoverflow.com/questions/18394147/recursive-sub-folder-search-and-return-files-in-a-list-python/18394205#18394205
def getFilesRecursive(func, path):
	return [func(dp, dn, filenames, f) for dp, dn, filenames in os.walk(path) for f in filenames]

def getDirectoryItemsNum(path):
	return len([fn for fn in getFilesRecursive(lambda a,b,c,fn:fn, path) if ((os.path.splitext(fn)[1].lower() in SUPPORTED_FORMATS) or SHOW_UNSUPPORTED_FORMATS)])

def shellEscape(arg):
	return '"'+arg.replace('\\', '\\\\').replace('"', '\\"')+'"'

def rootRelNoSlash(rootRel):
	return (rootRel+'/' if rootRel != '' else '')

#Take a video capture in the beginning of the video
#Stolen from https://gist.github.com/dplanella/5563018#file-gistfile2-py
#See also: https://wiki.ubuntu.com/Novacut/GStreamer1.0
def getVideoThumbnail(path):
	pipeline = Gst.parse_launch('playbin')
	pipeline.props.uri = 'file://' + os.path.abspath(path)
	pipeline.props.audio_sink = Gst.ElementFactory.make('fakesink', 'fakeaudio')
	pipeline.props.video_sink = Gst.ElementFactory.make('fakesink', 'fakevideo')
	pipeline.set_state(Gst.State.PAUSED)
	# Wait for state change to finish.
	pipeline.get_state(Gst.CLOCK_TIME_NONE)
	sample = pipeline.emit('convert-sample', Gst.Caps.from_string('image/jpeg'))
	if sample == None:
		raise IOError('Not a video');
	ret = sample.get_buffer() #Note: Don't merge this line with the line above. Somehow, it doesn't work! (probably because of C voodoo)
	pipeline.set_state(Gst.State.NULL)
	return ret.extract_dup(0, ret.get_size())

def getVideoDimension(path):
	pipeline = Gst.parse_launch('playbin')
	pipeline.props.uri = 'file://' + os.path.abspath(path)
	pipeline.props.audio_sink = Gst.ElementFactory.make('fakesink', 'fakeaudio')
	pipeline.props.video_sink = Gst.ElementFactory.make('fakesink', 'fakevideo')
	pipeline.set_state(Gst.State.PAUSED)
	pipeline.get_state(Gst.CLOCK_TIME_NONE)
	pad = pipeline.props.video_sink.get_static_pad('sink')
	caps = pad.get_current_caps()
	if caps == None:
		pipeline.set_state(Gst.State.NULL)
		raise IOError('Not a video file');
	struct = caps.get_structure(0)
	ret = (str(struct.get_int('width')[1]), str(struct.get_int('height')[1]))
	pipeline.set_state(Gst.State.NULL)
	return ret

def getMediaDuration(path):
	pipeline = Gst.parse_launch('playbin')
	pipeline.props.uri = 'file://' + os.path.abspath(path)
	pipeline.props.audio_sink = Gst.ElementFactory.make('fakesink', 'fakeaudio')
	pipeline.props.video_sink = Gst.ElementFactory.make('fakesink', 'fakevideo')
	pipeline.set_state(Gst.State.PAUSED)
	pipeline.get_state(Gst.CLOCK_TIME_NONE)
	sec = pipeline.query_duration(Gst.Format.TIME)[1]/10**9
	if sec == 0: #TODO: zero-length media doesn't mean that it isn't a media file. Should use a smarter way to detect it.
		pipeline.set_state(Gst.State.NULL)
		raise IOError('Not a video/music file');
	secStr = '{0:d}:{1:02d}'.format(int(sec/60), int(sec%60))
	pipeline.set_state(Gst.State.NULL)
	return secStr

########################
###Database functions###
########################
#Assumption:
DATABASE_VERSION = 0
class DataEntity:
	def __init__(self, mtime):
		self.mtime = float(mtime)

class Database:
	def __init__(self, filePath):
		self.filePath = filePath
		self.version = 0
		self.templateCheckSum = 0
		self.data = {}
		f = open(filePath, 'r')
		lines = f.read().splitlines() #Stolen from https://stackoverflow.com/questions/12330522/reading-a-file-without-newlines/12330535#12330535
		if len(lines) == 0:
			return
		self.version = int(lines[0])
		self.templateCheckSum = lines[1]
		if self.version == 0:
			lines = lines[2:]
			for l in lines:
				cols = l.split('\t')
				self.data[cols[0]] = DataEntity(cols[1])
		else:
			print('Error: unsupported database version')
	def save(self):
		f = open(self.filePath, 'w')
		f.write('{0}\n'.format(DATABASE_VERSION))
		f.write('{0}\n'.format(self.templateCheckSum))
		for key in self.data:
			f.write('{0}\t{1}\n'.format(key, self.data[key].mtime))
		f.close()

#################
###Match class###
#################
class Match:
	def __init__(self, fullMatch, matches, start, end):
		self._fullMatch = fullMatch
		self._matches = matches
		self._start = start
		self._end = end
	def __getitem__(self, i):
		return self._matches[i]
	def start(self):
		return self._start
	def end(self):
		return self._end
	def fullMatch(self):
		return self._fullMatch
	def __len__(self):
		return len(self._matches)

##########################
###generation functions###
##########################
def generateThumbnails(dest, database, rootRel, files):
	updated = False
	for f in files:
		#Generate thumbnails
		relInFile = 'assets/{0}'.format(rootRelNoSlash(rootRel)+f) #Path to the inFile relative to <dest>
		inFile = '{0}/{1}'.format(dest,relInFile)
		thumbnailFile = '{0}/thumbnails/{1}.jpg'.format(dest, rootRelNoSlash(rootRel)+f)
		#Check for support of file format
		if os.path.splitext(inFile)[1].lower() not in SUPPORTED_FORMATS and not SHOW_UNSUPPORTED_FORMATS:
			continue

		mtime = os.path.getmtime(inFile)
		#Check if thumbnail is already generated
		if relInFile in database.data and database.data[relInFile].mtime == mtime and os.path.exists(thumbnailFile):
			continue

		try:
			if os.path.splitext(inFile)[1].lower() in SUPPORTED_IMAGE_FORMATS:
				updated = True
				im = Image.open(inFile)
				im.thumbnail(THUMBNAIL_SIZE, Image.ANTIALIAS)
				database.data[relInFile] = DataEntity(mtime)
				im.save(thumbnailFile, 'JPEG')
			elif os.path.splitext(inFile)[1].lower() in SUPPORTED_VIDEO_FORMATS:
				updated = True
				im = Image.open(io.BytesIO(getVideoThumbnail(inFile)))
				im.thumbnail(THUMBNAIL_SIZE, Image.ANTIALIAS)
				database.data[relInFile] = DataEntity(mtime)
				im.save(thumbnailFile, 'JPEG')
			elif os.path.splitext(inFile)[1].lower() in SUPPORTED_MUSIC_FORMATS:
				#TODO: implement music thumbnail support
				#updated = True
				pass
			elif os.path.splitext(relInFile)[1].lower() in SUPPORTED_MISC_FORMATS:
				pass #No thumbnail for misc file by design
		except IOError:
			print('Warning: failed generating thumbnail for '+inFile)
	return updated

def findEnd(template, startCondition, endCondition, tags, i):
	assert tags[i][-1] == 'start'
	j = i
	recursionDepth = 1
	while recursionDepth > 0:
		j += 1
		if j >= len(tags):
			raise Exception('Error: Unterminated start: in '+tags[i][0]+' at line '+str(template.count("\n",0,tags[i].start())+1))
		if startCondition(j):
			recursionDepth += 1
		elif endCondition(j):
			recursionDepth -= 1

	assert tags[j][-1] == 'end'
	return j

def parseHtml(dest, database, rootRel, dirs, files, template, tags, i, j=-1, var=''):
	ret = ''
	while i < len(tags) and (j == -1 or i < j):
		if tags[i][0] == 'for': #Parse variable inside for loop
			if tags[i][2] == 'start':
				#Look for start-end pair of for loop
				innerJ = findEnd(template, lambda j: tags[j] == tags[i], lambda j: tags[j][0] == 'for' and tags[j][1] == tags[i][1] and tags[j][2] == 'end', tags, i)

				#generate the list of variables to be iterated thru the for loop
				varList = []
				if tags[i][1] == 'path':
					varList.append({'href':'index.{0}'.format(webFormat), 'num': str(getDirectoryItemsNum('{0}/assets/'.format(dest)))})

					dirPath = ''
					for r in rootRel.split('/'):
						if r == '': #''.split('/') returns ['']. We don't want this component.
							continue
						dirPath += r+'/'
						varList.append({'title':r, 'href':urllib.request.pathname2url('{0}.{1}'.format(dirPath[:-1], webFormat)).replace('/','-'), 'num': str(len(getFilesRecursive(lambda a,b,c,d:0, '{0}/assets/{1}'.format(dest, dirPath))))})
				elif tags[i][1] == 'files':
					for d in sorted(dirs):
						prefix = '{0}/thumbnails'.format(dest)
						thumbnailPaths = getFilesRecursive(lambda dp, dn, filenames, f:'./thumbnails/{0}'.format(os.path.join(dp, f)[len(prefix)+1:]), '{0}/{1}'.format(prefix, rootRelNoSlash(rootRel)+d))
						thumbnailPaths = [i for i in thumbnailPaths if (os.path.splitext(i)[1].lower() in SUPPORTED_IMAGE_FORMATS+SUPPORTED_VIDEO_FORMATS)]
						#shuffle the thumbnails so that the thumbnails generated is random
						random.seed(SHUFFLE_SEED)
						random.shuffle(thumbnailPaths)

						hrefPath = '{0}.{1}'.format( (rootRelNoSlash(rootRel)+d).replace('/','-'), webFormat )
						inFile = '{0}/assets/{1}'.format(dest, rootRelNoSlash(rootRel)+d)
						mtime = time.strftime(TIME_FORMAT, time.gmtime(os.path.getmtime(inFile)))
						size = humanReadable(os.path.getsize(inFile))
						varList.append({'title':d, 'href':urllib.request.pathname2url(hrefPath), 'num': str(getDirectoryItemsNum(inFile)), 'size': size, 'mtime': mtime, 'isDir':True, 'isImage':False, 'isVideo':False, 'isMusic':False, 'isMisc':False})
						index=0
						for t in thumbnailPaths:
							varList[-1]['thumbnails[{0}]'.format(index)] = urllib.request.pathname2url(t)
							index += 1
						if len(thumbnailPaths) > 0:
							varList[-1]['thumbnail'] = thumbnailPaths[0]
					for f in sorted(files):
						thumbnailPath = './thumbnails/{0}.jpg'.format(rootRelNoSlash(rootRel)+f)
						hrefPath = 'assets/{0}'.format(rootRelNoSlash(rootRel)+f)
						inFile = dest+'/'+hrefPath
						#Check for support of file format
						if os.path.splitext(inFile)[1].lower() not in SUPPORTED_FORMATS and not SHOW_UNSUPPORTED_FORMATS:
							continue
						mtime = time.strftime(TIME_FORMAT, time.gmtime(os.path.getmtime(inFile)))
						size = humanReadable(os.path.getsize(inFile))
						fileExtension = os.path.splitext(inFile)[1].lower()
						varList.append({'title':f, 'href':urllib.request.pathname2url(hrefPath), 'size': size, 'mtime': mtime, 'format':fileExtension, 'isDir':False, 'isImage':fileExtension in SUPPORTED_IMAGE_FORMATS, 'isVideo':fileExtension in SUPPORTED_VIDEO_FORMATS, 'isMusic':fileExtension in SUPPORTED_MUSIC_FORMATS, 'isMisc':fileExtension not in MEDIA_FORMATS})
						try:
							if varList[-1]['isImage']:
								dimension=Image.open(inFile).size
								varList[-1]['width'] = str(dimension[0])
								varList[-1]['height'] = str(dimension[1])
								varList[-1]['thumbnail'] = urllib.request.pathname2url(thumbnailPath)
							elif varList[-1]['isVideo']:
								varList[-1]['length'] = getMediaDuration(inFile)
								varList[-1]['width'], varList[-1]['height'] = getVideoDimension(inFile)
								varList[-1]['thumbnail'] = urllib.request.pathname2url(thumbnailPath)
							elif varList[-1]['isMusic']:
								varList[-1]['length'] = getMediaDuration(inFile)
						except IOError:
							print('Warning: failed generating parameters for '+inFile)
				else:
					raise Exception('Error: Invalid for variable in template: `'+tags[i][1]+'` in `'+tags[i].fullMatch()+'`'+' at line '+str(template.count("\n",0,tags[i].start())+1))

				#Add common elements to varList(e.g. i)
				for index in range(len(varList)):
					varList[index]['i'] = index
					varList[index]['isLast'] = (index==len(varList)-1)

				#parse the things inside the for loop
				for var in varList:
					ret += template[tags[i].end():tags[i+1].start()]
					ret += parseHtml(dest, database, rootRel, dirs, files, template, tags, i+1, innerJ, var)
				i = innerJ
		elif tags[i][0] == 'if': #Parse conditionally inside a for loop
			if j == -1: #Ensure that the if condition inside for loop
				raise Exception('Error: var outside for loop: in `'+tags[i].fullMatch()+'`'+' at line '+str(template.count("\n",0,tags[i].start())+1))
			if tags[i][2] == 'start':
				#Look for start-end pair of the if condition
				innerJ = findEnd(template, lambda j: tags[j][0] == 'if' and tags[j][1] != 'end', lambda j: tags[j][0] == 'if' and tags[j][1] == 'end', tags, i)
		
				#parse the things inside the if condition
				if bool(eval(tags[i][1], var)):
					ret += template[tags[i].end():tags[i+1].start()]
					ret += parseHtml(dest, database, rootRel, dirs, files, template, tags, i+1, innerJ, var)
				i = innerJ
		elif tags[i][0] == 'var': #Parse variable inside for loop
			if j == -1: #Ensure that var is inside for loop
				raise Exception('Error: var outside for loop: in `'+tags[i].fullMatch()+'`'+' at line '+str(template.count("\n",0,tags[i].start())+1))
			if tags[i][1] == 'convertedHref':
				format = tags[i][2]
				inFile = '{0}/{1}'.format(dest, urllib.request.url2pathname(var['href']))
				outHref = 'converted/{0}.{1}'.format(urllib.request.url2pathname(var['href'])[len('assets')+1:], format)
				outFile = '{0}/{1}'.format(dest, outHref)
				#If the file is already converted, use the existing converted file instead of reconverting it
				if os.path.exists(outFile) and os.path.getmtime(outFile) >= os.path.getmtime(inFile):
					ret += urllib.request.pathname2url(outHref)
					convertedFileList.append(outFile[len(dest)+1:])
				else:
					if os.path.exists(outFile):
						os.remove(outFile)
					command = ' '.join(tags[i][3:-1]).format(i=shellEscape(inFile), o=shellEscape(outFile))
					print('Converting '+inFile)
					if os.system(command) == 0:
						if os.path.exists(outFile):
							ret += urllib.request.pathname2url(outHref)
							convertedFileList.append(outFile[len(dest)+1:])
						else:
							print('Warning: command executed successfully but the output file is *not* found. Check your command executed: '+command)
							ret += tags[i][-1]
					else:
						#Conversion failed. Even if there's an output, it is useless. Don't use it!
						if os.path.exists(outFile):
							os.remove(outFile)
						ret += tags[i][-1]
			else:
				try:
					ret += var[tags[i][1]]
				except KeyError:
					if len(tags[i]) > 2 and tags[i][2]:
						ret += tags[i][2]
					else:
						raise Exception('Error: the var '+tags[i][1]+' doesn\'t exist in `'+tags[i].fullMatch()+'`'+' at line '+str(template.count("\n",0,tags[i].start())+1)+'\n You may want to specify else expression')
		elif tags[i][0] == 'fullTitle': #Parse the full title of the page
			ret += rootRel if rootRel != '' else tags[i][1]
		elif tags[i][0] == 'title': #Parse the title of the page
			ret += rootRel[:rootRel.rfind('/')] if rootRel.rfind('/') != -1 else (rootRel if rootRel != '' else tags[i][1])
		elif tags[i][0] == 'num': #Parse the number of files in the page, recursively
			ret += str(getDirectoryItemsNum('{0}/assets/{1}'.format(dest, rootRel)))
		elif tags[i][0].find('thumbnails') == 0: #Parse the title of the page
			prefix = '{0}/thumbnails'.format(dest)
			thumbnailPaths = getFilesRecursive(lambda dp, dn, filenames, f:'./thumbnails/{0}'.format(os.path.join(dp, f)[len(prefix)+1:]), '{0}/{1}'.format(prefix, rootRel))
			#shuffle the thumbnails so that the thumbnails generated is random
			random.seed(SHUFFLE_SEED)
			random.shuffle(thumbnailPaths)

			thumbnailIndex = int(re.search(r'thumbnails\[(.+)\]', tags[i][0])[0])
			try:
				ret += thumbnailPaths[thumbnailIndex]
			except IndexError:
				if len(tags[i]) >= 1 and tags[i][1]:
					ret += tags[i][1]
				else:
					raise Exception('Error: the var '+tags[i][0]+' doesn\'t exist in `'+tags[i].fullMatch()+'`'+' at line '+str(template.count("\n",0,tags[i].start())+1)+'\n You may want to specify else expression')
		elif tags[i][0] == 'mtime': #Parse the title of the page
			ret += time.strftime(TIME_FORMAT, time.gmtime(os.path.getmtime('{0}/assets/{1}'.format(dest, rootRel))))
		else:
			raise Exception('Error: Invalid for identifier in template: '+tags[i][1]+' in '+tags[i].fullMatch()+' at line '+str(template.count("\n",0,tags[i].start())+1))

		if i != len(tags)-1 and (j == -1 or i != j):
			ret += template[tags[i].end():tags[i+1].start()]
		i += 1
	return ret

def generateHtml(dest, template, database, rootRel, dirs, files):
	htmlFilePath = '{0}/{1}.{2}'.format(dest, rootRel.replace('/','-'), webFormat) if rootRel != '' else '{0}/index.{1}'.format(dest, webFormat)
	print('Generating HTML file: '+htmlFilePath)
	htmlFile = open(htmlFilePath, 'w')
	templateFile = open(template, 'r')
	template = templateFile.read()
	templateFile.close()

	#Regex behavior: extrace <?hgg a b c?>. a b c is extracted as group 1,3,5 respectively
	tags = [Match(i.group(0), i.group(1).split(), i.start(), i.end()) for i in re.finditer('<\?hgg\s*((\s+(.+?))+)\s*\?>', template)]

	if len(tags) == 0:
		htmlFile.write(template)
		htmlFile.close()
		return

	htmlFileBuffer = ''
	htmlFileBuffer += template[:tags[0].start()]
	htmlFileBuffer += parseHtml(dest, database, rootRel, dirs, files, template, tags, 0)
	htmlFileBuffer += template[tags[-1].end():]

	htmlFile.write(htmlFileBuffer)
	htmlFile.close()

#Remove unused files
def doGarbageCollection(dest, template, database, fullUpdate, update):
	print('Doing garbage collection...')
	assert os.path.exists(dest)

	directoryList = []
	filesList = []
	for root, dirs, files in os.walk(assetsPath):
		rootRel = root[len(assetsPath)+1:]
		directoryList += [rootRelNoSlash(rootRel)+d for d in dirs]
		filesList += [rootRelNoSlash(rootRel)+f for f in files]

	#Looks for old directory layout for the removal of web files
	oldDirectoryList = []
	#for f in database.data:
	#	d = f[:f.rfind('/')]
	#	dirRel = d[len('assets/'):]
	#	if dirRel not in oldDirectoryList and dirRel != '':
	#		oldDirectoryList.append(dirRel)

	#Predict the old directory structure by the thumbnails. It assumes that the directory structure of the thumbnails is not modified.
	thumbnailPath = dest+'/thumbnails'
	for root, dirs, files in os.walk(thumbnailPath):
		rootRel = root[len(thumbnailPath)+1:]
		for d in dirs:
			oldDirectoryList.append(rootRelNoSlash(rootRel)+d)


	#Remove old database entities
	for f in database.data.copy():
		if f[len('assets/'):] not in filesList:
			del database.data[f]
	database.save()

	#Remove old web files
	#FIXME: If the previous version of the template is in another format, then the old web files are not removed.
	webFormat = os.path.splitext(template)[1][1:]
	for d in oldDirectoryList:
		if d not in directoryList:
			oldFile = '{0}/{1}.{2}'.format(dest, d.replace('/','-'), webFormat)
			if os.path.exists(oldFile):
				os.remove(oldFile)

	#Remove old thumbnails and converted files that the original version in <dest>/assets is deleted
	#Note: do dest+'/thumbnails' last because it is used for old directory layout detection
	for path in [dest+'/converted', dest+'/thumbnails']:
		#Remove old files
		for root, dirs, files in os.walk(path):
			rootRel = root[len(path)+1:]
			for f in files:
				relFilePath = rootRelNoSlash(rootRel)+f
				if os.path.splitext(relFilePath)[0] not in filesList: #os.path.splitext(relFilePath)[0] removes the file extension
					oldFile = '{0}/{1}'.format(path,relFilePath)
					if os.path.exists(oldFile):
						os.remove(oldFile)
		#Remove old directories
		for root, dirs, files in os.walk(path):
			rootRel = root[len(path)+1:]
			for d in dirs:
				relDirPath = rootRelNoSlash(rootRel)+d
				if relDirPath not in directoryList:
					oldFile = '{0}/{1}'.format(path,relDirPath)
					if os.path.exists(oldFile):
						shutil.rmtree(oldFile)

	#Remove unused converted files that the original version exists, but the converted version is unused
	path = dest+'/converted'
	for root, dirs, files in os.walk(path):
		rootRel = root[len(path)+1:]
		for f in files:
			if ( fullUpdate or rootRel in update ) and 'converted/{0}'.format(f) not in convertedFileList:
				oldFile = '{0}/converted/{1}'.format(dest,f)
				if os.path.exists(oldFile):
					os.remove(oldFile)

convertedFileList = []
invalidArguments = False
garbageCollection = False
regenWebFiles = False

options = [i[1:] for i in sys.argv[1:] if i.find('-')==0]
for o in options:
	if o=='gc':
		garbageCollection = True
	if o=='regen-web-files':
		regenWebFiles = True
	else:
		print('Unknown option -'+o)
		invalidArguments = True

parameters = [i for i in sys.argv[1:] if i.find('-')!=0]

if not invalidArguments and len(parameters) == 2:
	lastDatabaseSaveTime = time.time()

	dest, template = parameters

	while len(dest) > 1 and dest[-1] == '/': #Remove the tailing /'s. Note that we won't remove the last / in case the user is spevifying / as the destination(what a stupid user!)
		dest = dest[:-1]

	print('Initializing...')
	mkdirIfNotExist(dest)
	mkdirIfNotExist('{0}/thumbnails'.format(dest))
	mkdirIfNotExist('{0}/assets'.format(dest))
	mkdirIfNotExist('{0}/converted'.format(dest))

	databasePath = '{0}/database'.format(dest)
	createIfNotExist(databasePath)
	database = Database(databasePath)

	readme = '{0}/README'.format(dest)
	if not os.path.exists(readme):
		with open(readme, 'w') as f:
			f.write(README_TEXT)

	fullUpdate = False #whether the gallery requires an full update
	update = []

	#Update the database if template is updated
	templateCheckSum = hashlib.sha224(open(template, 'rb').read()).hexdigest()
	if templateCheckSum != database.templateCheckSum:
		fullUpdate = True
		database.templateCheckSum = templateCheckSum

	print('Generating thumbnails in the following directories:')
	assetsPath = dest+'/assets'
	for root, dirs, files in os.walk(assetsPath):
		rootRel = root[len(assetsPath)+1:]
		print('{0}/{1}'.format(assetsPath,rootRel))
		for d in dirs: #Create the directories structure
			mkdirIfNotExist('{0}/thumbnails/{1}'.format(dest,rootRelNoSlash(rootRel)+d))
			mkdirIfNotExist('{0}/converted/{1}'.format(dest,rootRelNoSlash(rootRel)+d))
		if generateThumbnails(dest, database, rootRel, files):
			update.append(rootRel)
		if time.time()-lastDatabaseSaveTime > DATABASE_FLUST_INTERVAL:
			database.save()

	if fullUpdate or len(update)>0 or regenWebFiles:
		webFormat = os.path.splitext(template)[1][1:]
		#Do generation and update of gallery
		database.save()
		assetDir = '{0}/assets'.format(dest)
		for root, dirs, files in os.walk(assetDir):
			rootRel = root[len(assetDir)+1:]
			if fullUpdate or rootRel in update or regenWebFiles:
				generateHtml(dest, template, database, rootRel, dirs, files)

		#Generate index page
		files = os.listdir(assetDir)
	else:
		print('Gallery not updated. Not regenerating web files')

	if garbageCollection:
		doGarbageCollection(dest, template, database, fullUpdate, update)

	print('Generation completed!')
else:
	print('HTML Gallery Generator')
	print('Usage: '+sys.argv[0]+' <dest> <template> [-gc] [-regen-web-files]')
