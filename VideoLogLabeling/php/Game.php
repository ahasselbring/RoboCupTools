<?php
require_once 'Config.php';
require_once 'NaoLog.php';

class Game
{
    private $is_valid = false;
    private $id;
    private $path;
    private $date;
    private $team1;
    private $team2;
    private $half;
    private $event;

    private $logs = [];
    private $videos = [];

    private $errors = [];
    private $warnings = [];

    function __construct(SplFileInfo $path, Event $event) {
        $this->is_valid = preg_match('/'.Config::g('regex').'/', $path->getFilename(), $matches) === 1;
        if ($this->is_valid && $path->isReadable()) {
            $this->path = $path->getRealPath();
            $this->date = DateTimeImmutable::createFromFormat('Y-m-d_H-i-s',$matches[1]);
            $this->team1 = str_replace('_', ' ', $matches[2]);
            $this->team2 = str_replace('_', ' ', $matches[3]);
            $this->half = intval($matches[4]);
            $this->id = sha1($this->path);
            $this->event = $event;

            $this->init();
        } else {
            $this->errors[] = 'Game log path not valid or not readable!';
        }
    }

    private function init() {
        $path = $this->path . DIRECTORY_SEPARATOR . Config::g('dirs')['nao'];
        if (is_dir($path)) {
            $it = new DirectoryIterator($path);
            foreach($it as $file) {
                if (!$file->isDot() && $file->isDir()) {
                    $log = new NaoLog($file, $this->path, Config::g('dirs')['data']);
                    if ($log->isValid()) {
                        $this->logs[] = $log;
                    } else {
                        foreach ($log->getErrors() as $error) {
                            $this->errors[] = $this->getTeam1() . ' vs. ' . $this->getTeam2() . ', #' . $this->getHalf() . '/' . $log->getPlayer() . ': ' . $error;
                        }
                    }
                }
            }
            uasort($this->logs, function($a, $b){ return $a->getPlayer() - $b->getPlayer(); });
        } else {
            $this->errors[] = 'No log files!';
        }

        $path = $this->path . DIRECTORY_SEPARATOR . Config::g('dirs')['video'];
        if (is_dir($path)) {
            $it = new DirectoryIterator($path);
            foreach($it as $file) {
                if (!$file->isDot() && $file->isFile() && in_array(strtolower($file->getExtension()),Config::g('video_types'))) {
                    // TODO: own class for video !?
                    $this->videos[] = $file->getRealPath();
                }
            }
        } else {
            $this->errors[] = 'No video files!';
        }

        if (is_dir($this->path . DIRECTORY_SEPARATOR . Config::g('dirs')['gc'])) {
            // TODO: read gamecontroller files
        } else {
            $this->warnings[] = 'No gamecontroller files!';
        }
    }

    /**
     * @return bool
     */
    public function isValid()
    {
        return $this->is_valid;
    }

    /**
     * @return bool
     */
    public function hasErrors()
    {
        return count($this->errors) > 0;
    }
    /**
     * @return array
     */
    public function getErrors()
    {
        return $this->errors;
    }

    /**
     * @return string
     */
    public function getId()
    {
        return $this->id;
    }

    /**
     * @return DateTimeImmutable
     */
    public function getDate()
    {
        return $this->date;
    }

    /**
     * @return string
     */
    public function getDateString($format='d.m.Y, H:i:s')
    {
        return $this->date->format($format);
    }

    /**
     * @return string
     */
    public function getTeam1()
    {
        return $this->team1;
    }

    /**
     * @return string
     */
    public function getTeam2()
    {
        return $this->team2;
    }

    /**
     * @return int
     */
    public function getHalf()
    {
        return $this->half;
    }

    /**
     * @return array
     */
    public function hasLogs()
    {
        return count($this->logs) > 0;
    }

    /**
     * @return array
     */
    public function getLogs()
    {
        return $this->logs;
    }

    /**
     * @return array
     */
    public function getSize()
    {
        return count($this->logs);
    }

    /**
     * @return Event
     */
    public function getEvent()
    {
        return $this->event;
    }

    /**
     * @return bool
     */
    public function hasVideos()
    {
        return count($this->videos) > 0;
    }

    /**
     * @return array
     */
    public function getVideos()
    {
        return $this->videos;
    }

    /**
     * @return bool
     */
    public function hasLabels() {
        return $this->hasLogs() && array_filter($this->logs, function ($l) { return $l->hasLabels(); });
    }

    /**
     * Returns the label/event data as JSON string.
     * @return string
     */
    public function getLabelsAsJson() {
        $json = '[';
        foreach ($this->logs as $log) {
            $json .= $log->getLabelsAsJson() . ", \n";
        }
        $json .= ']';
        return $json;
    }
}