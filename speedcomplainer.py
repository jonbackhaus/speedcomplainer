import os
import sys
import argparse
import time
from datetime import datetime
import signal
import threading
import json
import random
from logger import Logger
from twython import Twython

shutdownFlag = False

def main(filename,argv):
    global configFile
    configFile = None

    if (argv.__len__() > 0):
        configFile = argv[0]

    print '======================================'
    print ' Starting Speed Complainer!           '
    print ' Lets get noisy!                      '
    print(' Config file: ' + str(configFile))
    print '======================================'

    global shutdownFlag
    signal.signal(signal.SIGINT, shutdownHandler)

    monitor = Monitor()
    time.sleep(10)
    try:
        print ('*********************##**************************')
        print('running monitor; time: ' + str(datetime.now()))
        monitor.run()
        # print('monitor runtime: ',datetime.now())
        for i in range(0, 6):
            if shutdownFlag:
                break
            time.sleep(10)
            # print('click sleep time: ',datetime.now())
        print ('####################**#######################')
    except Exception as e:
        print 'Error01: %s' % e
        sys.exit(1)
    sys.exit()


def shutdownHandler(signo, stack_frame):
    global shutdownFlag
    print 'Got shutdown signal (%s: %s).' % (signo, stack_frame)
    shutdownFlag = True


class Monitor():
    def __init__(self):
        self.lastPingCheck = None
        self.lastSpeedTest = None

    def run(self):
        if not self.lastPingCheck or (datetime.now() - self.lastPingCheck).total_seconds() >= 60:
            self.runPingTest()
            self.lastPingCheck = datetime.now()
            print('ping test started')

        if not self.lastSpeedTest or (datetime.now() - self.lastSpeedTest).total_seconds() >= 300:
            self.runSpeedTest()
            self.lastSpeedTest = datetime.now()
            print('Speed test started\n')

    def runPingTest(self):
        pingThread = PingTest()
        pingThread.start()

    def runSpeedTest(self):
        speedThread = SpeedTest()
        speedThread.start()


class PingTest(threading.Thread):
    def __init__(self, numPings=3, pingTimeout=2, maxWaitTime=6):
        global configFile
        super(PingTest, self).__init__()
        self.numPings = numPings
        self.pingTimeout = pingTimeout
        self.maxWaitTime = maxWaitTime
        if configFile is None:
            self.config = dict()
        else:
            self.config = json.load(open(configFile))
            assert isinstance(self.config, dict)
        if 'log' in self.config:
            self.logger = Logger(self.config['log']['type'], {'filename': self.config['log']['files']['ping']})

    def run(self):
        pingResults = self.doPingTest()
        if 'log' in self.config:
            self.logPingResults(pingResults)

    def doPingTest(self):
        print ('[' + str(self.ident) + '] executando ping \n')
        # import pdb; pdb.set_trace()
        if 'darwin' in sys.platform:
            # macOS response
            response = os.system('ping -c %s -W %s -w %s 8.8.8.8 > /dev/null 2>&1' % (
                self.numPings, (self.pingTimeout * 1000), self.maxWaitTime))
        elif 'win' in sys.platform:
            # Windows response
            response = os.system('ping -n %s -w %s www.google.com ' % (self.numPings, self.maxWaitTime))
        elif 'linux' in sys.platform:
            # linux response
            response = os.system('ping -c %s -W %s -w %s 8.8.8.8 > /dev/null 2>&1' % (
                self.numPings, (self.pingTimeout * 1000), self.maxWaitTime))
        else:
            print('[' + str(self.ident) + '] Sistema nao suportado')
            print('[' + str(self.ident) + '] ' + str(sys.platform))
            response = 1

        print ('[' + (str(self.ident) + '] Response:' + str(response) + '\n'))
        success = 0
        if response == 0:
            success = 1
        print('[' + str(self.ident) + '] success:' + str(success) + '\n')
        return {'date': datetime.now(), 'success': success}

    def logPingResults(self, pingResults):
        self.logger.log([pingResults['date'].strftime('%Y-%m-%d %H:%M:%S'), str(pingResults['success'])])


class SpeedTest(threading.Thread):
    def __init__(self):
        global configFile
        super(SpeedTest, self).__init__()
        if configFile is None:
            self.config = dict()
        else:
            self.config = json.load(open(configFile))
            assert isinstance(self.config, dict)
        if 'log' in self.config:
            self.logger = Logger(self.config['log']['type'], {'filename': self.config['log']['files']['speed']})

    def run(self):
        speedTestResults = self.doSpeedTest()
        if 'log' in self.config:
            self.logSpeedTestResults(speedTestResults)
        if 'twitter' in self.config:
            self.tweetResults(speedTestResults)

    def doSpeedTest(self):
        print ('[' + str(self.ident) + '] Starting speedtest \n')
        # run a speed test
        result = os.popen('speedtest-cli --simple').read()
        if 'Cannot' in result:
            return {'date': datetime.now(), 'uploadResult': 0, 'downloadResult': 0, 'ping': 0}
        print 'result: ' + str(result)
        # Result:
        # Ping: 529.084 ms
        # Download: 0.52 Mbit/s
        # Upload: 1.79 Mbit/s
        # import pdb; pdb.set_trace()

        resultSet = result.split('\n')
        try:
            pingResult = resultSet[0]
            downloadResult = resultSet[1]
            uploadResult = resultSet[2]
        except Exception as e:
            pingResult = 'Ping: 0.0 ms'
            downloadResult = 'Download: 0.0 Mbit/s'
            uploadResult = 'Upload: 0.0 Mbit/s'
            print '[' + str(self.ident) + '] ErrorISP Tratado: %s' % e

        pingResult = float(pingResult.replace('Ping: ', '').replace(' ms', ''))
        downloadResult = float(downloadResult.replace('Download: ', '').replace(' Mbit/s', ''))
        uploadResult = float(uploadResult.replace('Upload: ', '').replace(' Mbit/s', ''))

        print ('[' + str(self.ident) + '] Done speedtest')
        return {'date': datetime.now(), 'uploadResult': uploadResult, 'downloadResult': downloadResult,
                'ping': pingResult}

    def logSpeedTestResults(self, speedTestResults):
        self.logger.log([speedTestResults['date'].strftime('%Y-%m-%d %H:%M:%S'), str(speedTestResults['uploadResult']),
                         str(speedTestResults['downloadResult']), str(speedTestResults['ping'])])
        print('[' + str(self.ident) + '] Done log')

    def tweetResults(self, speedTestResults):
        twitter = self.config['twitter']
        thresholdMessages = self.config['tweetThresholds']
        message = None
        for (threshold, messages) in thresholdMessages.items():
            threshold = float(threshold)
            if speedTestResults['downloadResult'] < threshold and speedTestResults['downloadResult'] != 0.0:
                message = messages[random.randint(0, len(messages) - 1)].replace('{tweetTo}',
                                                                                 self.config['tweetTo']).replace(
                    '{internetSpeed}', self.config['internetSpeed']).replace('{downloadResult}',
                                                                             str(speedTestResults['downloadResult']))
                print ('[' + str(self.ident) + '] message:', message)
        if message:
            api = Twython(twitter['consumerKey'],
                          twitter['consumerSecret'],
                          twitter['token'],
                          twitter['tokenSecret'])

            if api:
                api.update_status(status=message)
            else:
                print ('[' + str(self.ident) + '] No API')
        else:
            if speedTestResults['downloadResult'] == 0.0:
                print('[' + str(
                    self.ident) + '] speedtest-cli: Unsupported platform')
            else:
                print ('[' + str(self.ident) + '] Internet dentro dos padroes estabelecidos')
        print('[' + str(self.ident) + '] Done tweetResult')


class DaemonApp():
    def __init__(self, pidFilePath, stdout_path='/dev/null', stderr_path='/dev/null'):
        self.stdin_path = '/dev/null'
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path
        self.pidfile_path = pidFilePath
        self.pidfile_timeout = 1

    def run(self):
        main(__file__, sys.argv[1:])


if __name__ == '__main__':
    main(__file__, sys.argv[1:])

    workingDirectory = os.path.basename(os.path.realpath(__file__))
    stdout_path = '/dev/null'
    stderr_path = '/dev/null'
    fileName, fileExt = os.path.split(os.path.realpath(__file__))
    pidFilePath = os.path.join(workingDirectory, os.path.basename(fileName) + '.pid')
    from daemon import runner

    dRunner = runner.DaemonRunner(DaemonApp(pidFilePath, stdout_path, stderr_path))
    dRunner.daemon_context.working_directory = workingDirectory
    dRunner.daemon_context.umask = 0o002
    dRunner.daemon_context.signal_map = {signal.SIGTERM: 'terminate', signal.SIGUP: 'terminate'}
    dRunner.do_action()
