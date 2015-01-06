# HTML Gallery Generator

## Features

* Generate image&video thumbnails
* Only regenerates contents that are required
* Customizable with template
* Capable for generating static and dynamic webpages(Despite the name HTML gallery generator, it can generate php/python/other gallery)
* Automatic conversion of video with custom command for better video compatibility
* wide number of attributes available. See the documentation below
* for and if statements support

## Showcase

* template.html([view generated gallery](http://hgg.sadale.duckdns.org/template.html/)) - A gallery template using semantic-ui. Recommended if you don't want to write your own template.
* templateNoJavascript.html([view generated gallery](http://hgg.sadale.duckdns.org/templateNoJavascript.html/)) - A simple gallery template. Read this example if you want to create your own template.
* templateNoJavascript4.html([view generated gallery](http://hgg.sadale.duckdns.org/templateNoJavascript4.html/)) - Based on templateNoJavascript.html. It shows 4 thumbnails for directories.
* template.php([view generated gallery](http://hgg.sadale.duckdns.org/template.php/)) - Based on template.html. It displays the modification time of the script at the bottom(php required).
* templateConvertVideo.html([view generated gallery](http://hgg.sadale.duckdns.org/templateConvertVideo.html/)) - Based on template.html. It convert the video to mp4 format that is supported by most Android devices

## License

* hgg.py: The BSD 2-Clause License
* Everything inside ./example/semantic-ui: The MIT License(as of 03/01/2015). [(Project homepage)](http://semantic-ui.com/)
* Everything else: public domain

## Requirements

* Linux. Not tested on other Operating System
* Python 3
* python3-pil
* python3-gst-1.0
* gstreamer1.0-plugins-good (optional, for additional video/audio support)
* gstreamer1.0-plugins-bad (optional, for additional video/audio support)
* gstreamer1.0-plugins-ugly (optional, for additional video/audio support)

On Ubuntu:

```
sudo apt-get install python3-pil python3-gst-1.0 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly
```

## Usage

```
hgg.py <dest> <template> [-gc] [-regenWebFiles]
```

* `-gc` enables garbage collection
* `-regen-web-files` forces regeneration of web files
* To regenerate thumbnails or converted files, you have to delete the directory `thumbnail/` or `converted/` manually.
* The web files generated has the same file extension as the `<template>`
* You may want to modify the `CONFIGURATION` section in `hgg.py`

## Getting Started

1. Run `hgg.py example template.html`
2. After the generation is completed, open `./example/index.html` in your browser
* You may want to:
	* Update the content in `./example/assets/` and run the command again
	* Try another template, or create your own template.
	* Start a new gallery. **Remember to copy `./example/semantic-ui` to `path/to/new/gallery/semantic-ui` if you are using `template.html` or other template that use semantic-ui**

## Directory Layout

```
gallery/
	assets/
		aaa/
			aaa.jpg
			bbb.mov
		bbb/
			ccc/
				...
			...
	thumbnails/
		aaa/
			aaa.jpg.jpg
			bbb.mov.jpg
		bbb/
			ccc/
				...
			...
	converted/
		aaa/
			bbb.mov.mp4 #Note: the converted files are only available if you make a custom command in template to generate it
		bbb/
			ccc/
				...
			...
	css-javascript/ #Note: You need to create this directory yourself
		...
	database
	README
	index.html
	aaa.html
	bbb.html
	bbb-ccc.html
```

## Template documentation

```
for arg start, for arg end:
	path -- elements of each path component of the gallery
		attributes:
			title(for non-index only)(HTML character escaped)
			href
			num
		Example: 'a/b/c' returns ['a', 'b', 'c']
	files -- the files in the current directory, sorted alphabetically
		attributes:
			title(HTML character escaped)
			thumbnail(URL quoted. For directory: defined only if there is picture inside a folder. For files: defined if it is image or video file)
			thumbnails[n](URL quoted. n is index. directory only)
			href(URL quoted)
			convertedHref(URL quoted. see var convertedHref)
			num(number of files in a directory, counted recursively. Directory only)
			size
			width(image&video only)
			height(image&video only)
			length(video&music only)
			mtime
			format(file extension in lower case, file only)
			isDir
			isImage
			isVideo
			isMusic
			isMisc
	common attributes:
		i: the index of the current loop
		isLast: whether it is the last element in the loop
if expr start, if expr end:
	conditionally print expression inside a for expression. Prints if the expr is evaluated to True
	expr: the expression to be evaluated. Example: isLast==False; i%5==0; (i%5==0)&(i!=0)
	To to and, or, xor operation, use single &, |, ^ respectively. This is a dirty hack to make these operation works without whitespace.
	Warning: eval() is used for parsing if statements. It can be dangerous.
var arg
	parse the loop argument arg.
var arg else
	parse the loop argument arg. If failed, parse else instead.
var convertedHref format command commandArg1 commandArg2 ... else
	converts the file into another format with the use of external command. Then parse the URL quoted href to the converted file
	The converted file is stored to <dest>/converted/foo/bar/originalFilename.format
	If the mtime of the converted file < mtime of the original file, the file will be reconverted.
	format -- the file extension of the converted file format
	command commandArg1 commandArg2 ... -- The command to convert the file. {i} is parsed as the input path and {o} is parsed as the output path
	else -- if the command returns non-zero, this string is parsed instead of the href of the converted file
	Remarks: If you convert a file twice with the same format, it is reconverted only if the input file is newer than the converted file
	Warning: os.system() is used for parsing this statement. It can be very dangerous.
title <indexTitle>
	title of the current directory(example: trip)
	For index, the parameter <indexTitle> is parsed instead. If you want to use whitespace, use ;nbsp&
fullTitle <indexTitle>
	full title of the current directory(example: 2013/trip)
	For index, the parameter <indexTitle> is parsed instead. If you want to use whitespace, use ;nbsp&
num
	number of items in the current directory
thumbnails[n] else
	thumbnails of the current directory
	if the index is invalid, else is parsed instead.
mtime
	mtime of the current directory
```

Warning: HTML template of this script is capable for running dangerous commands. For better security:

* Checks `<?hgg var convertedHref [... ... ...] [else]>` before using it. This script runs `[... ... ...]` as system command
* Checks `<?hgg if [expr]>` in template before using it. This script evaluates `[expr]` in python
* Remove write permission of the template file a.k.a. `og-w`
* Don't run this script as root unless you need to
