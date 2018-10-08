import glob
import json
import math
import os
import re
import io

from parsers import BehaviorParser
from .Config import config


class Log:

    def __init__(self, game, dir, data_dir):
        self.game = game
        self.directory = dir
        self.data_directory = data_dir

        self.file = None
        self.sync_file = None
        self.labels = []
        self.labels_data = None

        self.player_number = 0
        self.nao = None
        self.robot = None

        self.parse_info()
        self.scan_data()

    def parse_info(self):
        log_file = os.path.join(self.directory, config['log']['name'])
        if os.path.isfile(log_file):
            self.file = log_file

        m = re.match(config['log']['regex'], os.path.basename(self.directory))

        self.player_number = m.group(1)
        self.nao = m.group(2)
        self.robot = m.group(3)

    def scan_data(self):
        if os.path.isdir(self.data_directory):
            # set the sync information
            sync_file = os.path.join(self.data_directory, config['log']['sync'])
            if os.path.isfile(sync_file):
                self.sync_file = { 'file': sync_file }
                # TODO: parse this file?

            self.labels = glob.glob(self.data_directory+'/'+config['log']['labels'][0]+'*'+config['log']['labels'][1])

    def __read_labels(self):
        if self.labels_data is None:
            label_file = self.data_directory+'/'+config['log']['labels'][0]+config['log']['labels'][1]
            if os.path.isfile(label_file):
                self.labels_data = json.load(io.open(label_file, 'r', encoding='utf-8'))

        return self.labels_data

    def parsed_actions(self):
        data = self.__read_labels()
        if data and 'parsed_actions' in data:
            return data['parsed_actions']
        return []

    def has_syncing_file(self):
        return self.sync_file is not None

    def create_default_syncing_file(self):
        print(self.directory, self.data_directory, self.file)
        if self.file:
            point = self.find_first_ready_state(self.file)
            if point:
                self.sync_file = os.path.join(self.data_directory, config['log']['sync'])
                with open(self.sync_file, 'w') as sf:
                    sf.writelines([
                        '# generated by python script\n'
                        'sync-time-video=0.0\n',
                        'sync-time-log='+str(point[1]/1000.0)+'\n',
                        'video-file='+(self.game.videos[0] if self.game.videos else '')+'\n'
                    ])

    def find_first_ready_state(self, file):
        parser = BehaviorParser.BehaviorParser()
        log = BehaviorParser.LogReader(file, parser)

        for frame in log:
            if 'BehaviorStateComplete' in frame.messages:
                m, o = frame["BehaviorStateComplete"]
            else:
                m, o = frame["BehaviorStateSparse"]

            if m['game.state'] == 1:
                log.close()
                return frame.number, frame['FrameInfo'].time

        return None

    def has_label_file(self):
        return len(self.labels) > 0

    def create_label_file(self, actions):
        # print(self.directory, self.data_directory, self.file)
        parser = BehaviorParser.BehaviorParser()
        log = BehaviorParser.LogReader(self.file, parser)
        data = self.__read_labels()
        # update or create data structure
        if data is not None:
            data['parsed_actions'] = list(set(data['parsed_actions']) | set(actions.keys()))
        else:
            data = { 'parsed_actions': list(actions.keys()), 'intervals': {}, 'start': 0, 'end': 0 }
        tmp = {}

        if log.size > 0:
            # ignore the first frame and set the second frame time as starting point of this log file
            data['start'] = log[1]["FrameInfo"].time / (1000.0 * 60) * 60

        # enforce the whole log being parsed (this is necessary for older game logs)
        for frame in log:
            s, o = (None, None)
            if "BehaviorStateComplete" in frame.messages:
                s, o = frame["BehaviorStateComplete"]
            if "BehaviorStateSparse" in frame.messages:
                s, o = frame["BehaviorStateSparse"]
            # enforce parsing FrameInfo
            fi = frame["FrameInfo"]

            # got valid data
            if s and o and fi:
                for a in actions:
                    # check if an action applies
                    if actions[a](s, o):
                        # begin an interval for this action
                        if a not in tmp or tmp[a] is None:
                            tmp[a] = { 'type': a,
                                       'frame': fi.frameNumber,
                                       'begin': fi.time / (1000.0 * 60) * 60,
                                       "pose": {"x": s["robot_pose.x"], "y": s["robot_pose.y"], "r": s["robot_pose.rotation"] * math.pi / 180},
                                       "ball": {"x": s["ball.position.field.x"], "y": s["ball.position.field.y"]} }
                        elif tmp[a]['frame'] == fi.frameNumber - 1:
                            # continue this action interval
                            tmp[a]['frame'] = fi.frameNumber
                    elif a in tmp and tmp[a] is not None:
                        # there's an open interval, close it
                        tmp[a]['end'] = fi.time / (1000.0 * 60) * 60
                        interval_id = '{}_{}'.format(tmp[a]['frame'], a)
                        data['intervals'][interval_id] = tmp[a]
                        del tmp[a]

            # update the time of the last frame
            if fi: data['end'] = fi.time / (1000.0 * 60) * 60

        label_file = self.data_directory + '/' + config['log']['labels'][0] + config['log']['labels'][1]
        json.dump(data, open(label_file, 'w'), indent=4, separators=(',', ': '))
        self.labels.append(label_file)
        log.close()

    def __repr__(self):
        return "Nao{} #{}".format(self.nao, self.player_number)
