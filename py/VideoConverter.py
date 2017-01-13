#!/usr/bin/env python
#encoding: UTF-8

import sys
import os
import argparse
import logging
import mimetypes
import re
#from subprocess import Popen, PIPE
import subprocess
import json

'''
    TODO:
        * search for video files
        * determine which files are missing (thumbnail, format, quality)
        * start converting files (ask before?)
        * show progress
        * implement ability to get progress from extern (eg. php)
    INFO:
        * https://github.com/senko/python-video-converter/blob/master/converter/ffmpeg.py
'''

class VideoConverter:
    def __init__(self, video, config):
        self.video = video
        self.config = config
        self.todo = {}

    def analyze(self):
        for conf in self.config:
            for f in self.video.files:
                hasAllAttributes = True
                for attr in conf:
                    hasAllAttributes = hasAllAttributes and attr in f and (conf[attr] == f[attr] if not isinstance(f[attr], list) else conf[attr] in f[attr])
                if hasAllAttributes:
                    conf['todo'] = False
                    break
            if 'todo' not in conf:
                conf['todo'] = True
        self.todo = [ i for i in self.config if i['todo'] ]
        return self.todo
    
    def getTodo(self):
        return self.todo if self.todo else self.analyze()
    
    def __str__(self):
        result = self.video.getKey()
        for todo in self.getTodo():
            result += '\n\t* ' + str(todo)
        #print self.getTodo()
        return result
    
class VideoLocator:
    def search(self, path):
        assert os.path.isdir(path), 'Not a directoy!'
        result = {}
        filter = re.compile('video/.*')
        mimetypes.init() # do we need this?!
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                f = os.path.join(dirpath, filename)
                # filter video files
                if mimetypes.guess_type(f)[0] is not None and filter.match(mimetypes.guess_type(f)[0]):
                    video = VideoFile(f)
                    if video.getKey() in result:
                        result[video.getKey()].add(video)
                    else:
                        result[video.getKey()] = video
        return result

class VideoFile:
    def __init__(self, file):
        file = os.path.abspath(file)
        m = re.match('(?P<name>[^\.]+)(\.(?P<config>.+))?\.(?P<ext>.+)', os.path.basename(file))
        #print m.groups(), m.group('config')
        self.path = os.path.dirname(file)
        self.name = m.group('name')
        self.files = [ {
            'filename': file,
            'extension': m.group('ext').lower(),
            'config': self._parseConfig(m.group('config'))
        } ]
        #print self.files
    
    def add(self, video):
        if isinstance(video, str):
            video = VideoFile(video)
        if self.getKey() != video.getKey():
            getLogger().debug('Files doesn\'t represents same video content!')
        else:
            self.files += video.files
    
    def __repr__(self):
        return str(self.files)
    
    def __str__(self):
        return str(self.__repr__())
    
    def getKey(self):
        return self.path + os.sep + self.name
    
    def analyze(self):
        for file in self.files:
            file.update(ffmpeg.getMediaInfo(file['filename']))
    
    def _parseConfig(self, string):
        if string is None:
            return None
        
        config = {}
        for part in string.split('.'):
            if part == 'an':
                config['muted'] = True
            elif re.match('\d+p', part):
                config['height'] = part
        return config

    def getExtensions(self):
        return set([ f['extension'] for f in self.files if 'extension' in f ])
    
    def getHeights(self):
        return set([ f['height'] for f in self.files if 'height' in f ])
    
    def getMaxHeight(self):
        return max(self.getHeights())
    
    def getConfigs(self, attributes=None):
        result = []
        for f in self.files:
            print f.values()
            #print f.keys()
                
        

class FFMpeg:
    def __init__(self, ffmpeg_path='ffmpeg', ffprobe_path='ffprobe'):
        # check 'ffmpeg'
        ffmpeg_path = self.which(ffmpeg_path) if '/' not in ffmpeg_path else ffmpeg_path
        try:
            subprocess.check_output([ffmpeg_path, '-version'], stderr=subprocess.STDOUT)
            self.ffmpeg_path = ffmpeg_path
        except Exception as e:
            getLogger().error('Couldn\'t find ffmpeg!')
            self.ffmpeg_path = None
        # check 'ffprobe'
        ffprobe_path = self.which(ffprobe_path) if '/' not in ffprobe_path else ffprobe_path
        try:
            subprocess.check_output([ffprobe_path, '-version'], stderr=subprocess.STDOUT)
            self.ffprobe_path = ffprobe_path
        except Exception as e:
            getLogger().error('Couldn\'t find ffprobe!')
            self.ffprobe_path = None

    def which(self, name):
        try:
            return subprocess.check_output(['which', name]).strip()
        except:
            path = os.environ.get('PATH', os.defpath)
            for d in path.split(':'):
                fpath = os.path.join(d, name)
                if os.path.exists(fpath) and os.access(fpath, os.X_OK):
                    return fpath
        return name
    
    def getMediaInfo(self, file):
        info = {}
        try:
            # loading media info with ffprobe as json
            data = subprocess.check_output([self.ffprobe_path, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', file], stderr=subprocess.STDOUT)
            # TODO: check result on error?!?
            js = json.loads(data)
            # set the infos
            info['filename'] = js['format']['filename']
            info['size'] = int(js['format']['size'])
            info['duration'] = float(js['format']['duration'])
            info['bitrate'] = int(js['format']['bit_rate'])
            info['format'] = js['format']['format_name'].split(',')
            for stream in js['streams']:
                if stream['codec_type'] == 'video':
                    # log multiple video streams
                    if 'width' in info:
                        getLogger().debug('There seems to more than one video stream in the file (%s)', file)
                    info['width'] = stream['width']
                    info['height'] = stream['height']
        except Exception, e:
            getLogger().error('An error occurred: %s', e)
        return info
    
    def convert(self, file, params):
        # TODO: !
        pass


def getArguments():
	parser = argparse.ArgumentParser(description='TODO ...') # TODO ...
	parser.add_argument('-f', '--file', 	action='store', help='video file which should be converted.')
        parser.add_argument('-d', '--directory',action='store', help='log directory where the video files should be searched.')
        parser.add_argument('-v' ,'--verbose', 	action='store_true', help='print everything')
	return parser


def getLogger(suffix=None):
    return logging.getLogger(os.path.splitext(os.path.basename(__file__))[0]+('.'+suffix if suffix is not None else ''))

if __name__ == "__main__":
    args = getArguments().parse_args()
    
    # setup logger
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO )
    
    # setup ffmpeg wrapper class
    ffmpeg = FFMpeg()
    
    formats = [ { 'format': 'mp4',  'height': 144 },
                { 'format': 'webm', 'height': 144 },
                { 'format': 'mp4',  'height': 240 },
                { 'format': 'webm', 'height': 240 },
                { 'format': 'mp4',  'height': 360 },
                { 'format': 'webm', 'height': 360 },
                { 'format': 'mp4',  'height': 480 },
                { 'format': 'webm', 'height': 480 },
                { 'format': 'mp4',  'height': 720 },
                { 'format': 'webm', 'height': 720 }, ]
                
    todo_list = []
    
    if args.file is not None:
        # TODO: process file
        assert os.path.isfile(args.file), 'Not a file!'
        files = VideoLocator().search(os.path.dirname(args.file))
        for f in files:
            if args.file.startswith(f):
                files[f].analyze()
                converter = VideoConverter(files[f], formats)
                todo_list.append(converter)
    elif args.directory is not None:
        # TODO: process log directory
        try:
            files = VideoLocator().search(args.directory)
            for key in files:
                files[key].analyze()
                #files[key].getConfigs()
                #print files[key]
                converter = VideoConverter(files[key], formats)
                todo_list.append(converter)
                #print converter.getTodo()
                #print files[key].getKey(), files[key].getExtensions(), files[key].getHeights()
        except Exception as e:
            getLogger().error(e)
    else:
        getArguments().print_help()
        exit()

    print 'The following would be converted:'
    for i in todo_list:
        print '  - ', i
    
    choice = raw_input("\nHow to continue? (cancel [C], convert all [A], ask every file [F], ask every format configuration [M]\n-> ")
    while choice.lower() not in ['c','a','f','m']:
        choice = raw_input("[C,A,F,M]-> ")
    
    if choice.lower() == 'c':
        exit()
    else:
        print 'do something'
        pass
    
    #print ffmpeg.getMediaInfo('/mnt/Daten/Development/NaoTH/VideoLogLabeling/log/2016-07-01-outdoor-NTU/half2.mp4')
    #print ffmpeg.getMediaInfo('/mnt/Daten/Development/NaoTH/VideoLogLabeling/log/2016-07-01-outdoor-NTU/half2.webm')
    
    #t = Popen('pwd', shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
    #'/mnt/Daten/Development/NaoTH/VideoLogLabeling/log/2016-07-01-outdoor-NTU/half2.mp4', 
    #'/mnt/Daten/Development/NaoTH/VideoLogLabeling/log/2016-07-01-outdoor-NTU/half2.webm', 
    #'/mnt/Daten/Development/NaoTH/VideoLogLabeling/log/2016-07-01-outdoor-NTU/half2_1.mp4', 
    #'/mnt/Daten/Development/NaoTH/VideoLogLabeling/log/2016-07-01-outdoor-NTU/half2_1.webm'
    #ffprobe -v error -show_entries format=size,duration, -of flat /mnt/Daten/Development/NaoTH/VideoLogLabeling/log/2016-07-01-outdoor-NTU/half2.webm
    
    
    #py/VideoConverter.py -d "/mnt/Daten/Development/NaoTH/VideoLogLabeling/log"
    #py/VideoConverter.py -f /mnt/Daten/Development/NaoTH/VideoLogLabeling/log/2016-07-01-outdoor-NTU/video/half1.mp4
    
