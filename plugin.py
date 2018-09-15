#
#   Spotify Plugin
#
#   Daan Jansen, Coral Rosoff, 2018
#   https://github.com/DaanJJansen/domoticz-spotify
#

"""
<plugin key="Spotify" name="Spotify Plugin" author="djj" version="0.2" wikilink="https://github.com/DaanJJansen/domoticz-spotify" externallink="https://api.spotify.com">
    <params>
        <param field="Address" label="Domoticz IP Address" width="200px" required="true" default="localhost"/>
        <param field="Port" label="Domoticz Port" width="40px" required="true" default="8080"/>
        <param field="Username" label="Domoticz Username" width="200px" required="false" default=""/>
        <param field="Password" label="Domoticz Password" width="200px" required="false" default=""/>
        <param field="Mode4" label="Domoticz encoded credentials" width="200px" required="false" default=""/>
        <param field="Mode1" label="Client ID" width="200px" required="true" default=""/>
        <param field="Mode2" label="Client Secret" width="200px" required="true" default=""/>
        <param field="Mode3" label="Code" width="400px" required="true" default=""/>
        <param field="Mode5" label="Poll intervall" width="100px" required="true">
            <options>
                <option label="None" value=0/>
                <option label="30 seconds" value=1/>
                <option label="5 minutes" value=10 default="true"/>
                <option label="15 minutes" value=30/>
                <option label="30 minutes" value=60/>
                <option label="60 minutes" value=120/>
            </options>
        </param>
    	<param field="Mode6" label="Debug" width="75px">
    		<options>
        		<option label="True" value="Debug"/>
        		<option label="False" value="Normal"  default="True" />
    		</options>
    	</param>
    </params>
</plugin>
"""

try:
    import Domoticz

    local = False
except ImportError:
    local = True
    import fakeDomoticz as Domoticz
    from fakeDomoticz import Devices
    from fakeDomoticz import Parameters

import urllib.request
import urllib.error
import urllib.parse
import base64
import json
import time

# DEFINES
SPOTIFYDEVICES = 1
SPOTIFYPLAYBACK = 2


#############################################################################
#                      Domoticz call back functions                         #
#############################################################################
class BasePlugin:
    def __init__(self):
        self.spotifyToken = {"access_token": "",
                             "refresh_token": "",
                             "retrievaldate": ""
                             }
        self.spotifySearchParam = ["searchTxt"]
        self.tokenexpired = 3600
        self.spotArrDevices = {}
        self.spotPlaybackSelectorMap = {}
        self.spotifyAccountUrl = "https://accounts.spotify.com/api/token"
        self.spotifyApiUrl = "https://api.spotify.com/v1"
        self.heartbeatCounterPoll = 1
        self.blError = False

    def onStart(self):
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)

        for var in ['Mode1', 'Mode2', 'Mode3']:
            if Parameters[var] == "":
                Domoticz.Error('No client_id, client_secret and/or code is set in hardware parameters')
                self.blError = True
                return None

        if not self.getUserVar():
            self.blError = True
            return None

        for key, value in self.spotifyToken.items():
            if value == '':
                Domoticz.Log("Not all spotify token variables are available, let's get it")
                if not self.spotAuthoriseCode():
                    self.blError = True
                    return None
                break

        self.checkDevices()
        self.checkPlayback()

        Domoticz.Heartbeat(30)

    def checkDevices(self):
        Domoticz.Log("Checking if devices exist")

        if SPOTIFYDEVICES not in Devices:
            Domoticz.Log("Spotify devices selector does not exist, creating device")

            strSelectorNames = 'Off'
            dictOptions = self.buildDeviceSelector(strSelectorNames)

            Domoticz.Device(Name="devices", Unit=SPOTIFYDEVICES, Used=1, TypeName="Selector Switch", Switchtype=18,
                            Options=dictOptions, Image=8).Create()
        else:
            self.updateDeviceSelector()

    def checkPlayback(self):
        Domoticz.Log("Checking if playback controller exist")

        strPlaybackOperations = 'Off|Play|Pause|Next|Previous'

        if SPOTIFYPLAYBACK not in Devices:
            Domoticz.Log("Spotify playback controller does not exist, creating device")

            dictOptions = {"LevelActions": strPlaybackOperations,
                           "LevelNames": strPlaybackOperations,
                           "LevelOffHidden": "false",
                           "SelectorStyle": "0"}

            Domoticz.Device(Name="playback", Unit=SPOTIFYPLAYBACK, Used=1, TypeName="Selector Switch", Switchtype=18,
                            Options=dictOptions, Image=8).Create()

        else:
            Domoticz.Debug("Playback controller already exist")

        dictValue = 0
        for item in strPlaybackOperations.split('|'):
            self.spotPlaybackSelectorMap[dictValue] = item
            dictValue = dictValue + 10

    def updateDeviceSelector(self):
        Domoticz.Debug("Updating spotify devices selector")
        strSelectorNames = Devices[SPOTIFYDEVICES].Options['LevelNames']
        dictOptions = self.buildDeviceSelector(strSelectorNames)

        if dictOptions != Devices[SPOTIFYDEVICES].Options:
            Devices[SPOTIFYDEVICES].Update(nValue=Devices[SPOTIFYDEVICES].nValue, sValue=Devices[SPOTIFYDEVICES].sValue,
                                           Options=dictOptions)

    def buildDeviceSelector(self, strSelectorNames):
        spotDevices = self.spotDevices()
        Domoticz.Debug('JSON Returned from spotify listed available devices: ' + str(spotDevices))

        strSelectorActions = ''

        lstSelectorNames = strSelectorNames.split("|")

        x = 1
        while x < len(lstSelectorNames):
            strSelectorActions += '|'
            x += 1

        intCounter = (len(lstSelectorNames) * 10)

        for device in spotDevices['devices']:
            if device['name'] not in lstSelectorNames:
                strSelectorNames += '|' + device['name']
                strSelectorActions += '|'
                self.spotArrDevices.update({str(intCounter): device['id']})
                intCounter += 10
            else:
                self.spotArrDevices.update({str(lstSelectorNames.index(device['name']) * 10): device['id']})

        Domoticz.Debug('Local array listing selector level with device ids: ' + str(self.spotArrDevices))

        dictOptions = {"LevelActions": strSelectorActions,
                       "LevelNames": strSelectorNames,
                       "LevelOffHidden": "false",
                       "SelectorStyle": "1"}

        return dictOptions

    def spotGetBearerHeader(self):
        tokenSecElapsed = time.time() - float(self.spotifyToken['retrievaldate'])
        if tokenSecElapsed > self.tokenexpired:
            Domoticz.Log('Token expired, getting new one using refresh_token')
            self.spotGetRefreshToken()

        return {"Authorization": "Bearer " + self.spotifyToken['access_token']}

    def spotDevices(self):
        try:
            url = self.spotifyApiUrl + '/me/player/devices'
            headers = self.spotGetBearerHeader()

            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req)

            strResponse = response.read().decode('utf-8')
            return json.loads(strResponse)

        except urllib.error.URLError as err:
            Domoticz.Error("Unkown error: code: {code}, msg: {message}".format(
                code=str(err.code), message=str(err.args)))
            return None

    def getUserVar(self):
        try:
            variables = DomoticzAPI({'type': 'command', 'param': 'getuservariables'})

            if variables:
                valuestring = ""
                missingVar = []
                lstDomoticzVariables = list(self.spotifyToken.keys()) + self.spotifySearchParam
                if "result" in variables:
                    for intVar in lstDomoticzVariables:
                        intVarName = Parameters["Name"] + '-' + intVar
                        try:
                            result = next((item for item in variables["result"] if item["Name"] == intVarName))
                            if intVar in self.spotifyToken:
                                self.spotifyToken[intVar] = result['Value']
                            Domoticz.Debug(str(result))
                        except:
                            missingVar.append(intVar)
                else:
                    for intVar in lstDomoticzVariables:
                        missingVar.append(intVar)

                if len(missingVar) > 0:
                    strMissingVar = ','.join(missingVar)
                    Domoticz.Log("User Variable {} does not exist. Creation requested".format(strMissingVar))
                    for variable in missingVar:
                        DomoticzAPI({"type": "command", "param": "saveuservariable",
                                     "vname": Parameters["Name"] + '-' + variable, "vtype": "2", "vvalue": ""})

                return True
            else:
                raise Exception("Cannot read the uservariable holding the persistent variables")

        except Exception as error:
            Domoticz.Error(str(error))

    def saveUserVar(self):
        try:
            for intVar in self.spotifyToken:
                intVarName = Parameters["Name"] + '-' + intVar
                DomoticzAPI({"type": "command", "param": "updateuservariable", "vname": intVarName, "vtype": "2",
                             "vvalue": str(self.spotifyToken[intVar])})
        except Exception as error:
            Domoticz.Error(str(error))

    def spotGetRefreshToken(self):
        try:
            url = self.spotifyAccountUrl
            headers = self.returnSpotifyBasicHeader()

            data = {'grant_type': 'refresh_token',
                    'refresh_token': self.spotifyToken['refresh_token']}
            data = urllib.parse.urlencode(data)

            req = urllib.request.Request(url, data.encode('ascii'), headers)
            response = urllib.request.urlopen(req)

            strResponse = response.read().decode('utf-8')
            Domoticz.Debug('Spotify response accestoken based on refresh: ' + str(strResponse))

            jsonResponse = json.loads(strResponse)

            self.saveSpotifyToken(jsonResponse)
        except:
            Domoticz.Error('Seems something with wrong with token response from spotify')

    def returnSpotifyBasicHeader(self):
        client_id = Parameters["Mode1"]
        client_secret = Parameters["Mode2"]
        login = client_id + ':' + client_secret
        base64string = base64.b64encode(login.encode())
        header = {'Authorization': 'Basic ' + base64string.decode('ascii')}
        Domoticz.Debug('For basic headers using client_id: {client_id}, client_secret: {client_secret}'.format(
            client_id=client_id, client_secret=client_secret))

        return header

    def spotAuthoriseCode(self):
        try:
            code = Parameters["Mode3"]
            url = self.spotifyAccountUrl
            data = {'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': 'http://localhost'}
            Domoticz.Debug('Getting tokens using data: {}'.format(data))
            data = urllib.parse.urlencode(data)

            headers = self.returnSpotifyBasicHeader()
            Domoticz.Debug('Getting tokens using header: {}'.format(headers))

            try:
                req = urllib.request.Request(url, data.encode('ascii'), headers)
                response = urllib.request.urlopen(req)

                strResponse = response.read().decode('utf-8')
                Domoticz.Debug('Spotify tokens based on authorisation code: ' + str(strResponse))
                jsonResponse = json.loads(strResponse)

                self.saveSpotifyToken(jsonResponse)

                return True

            except urllib.error.HTTPError as err:
                errmsg = "Error occured in request for getting acces_tokens from Spotify, error code: " \
                         "{code}, reason: {reason}.".format(code=err.code, reason=err.reason)
                if err.code == 400:
                    errmsg += " Seems either client_id, client_secret or code is incorrect. " \
                              "Please note that the code received from Spotify could only be used once. " \
                              "Please get a new one from spotify."
                Domoticz.Error(errmsg)

        except Exception as error:
            Domoticz.Error(error)

    def saveSpotifyToken(self, response):
        try:
            for intVar in self.spotifyToken:
                if intVar in response:
                    self.spotifyToken[intVar] = response[intVar]
            self.spotifyToken['retrievaldate'] = time.time()
            Domoticz.Log('Succesfully got spotify tokens, saving data in user domoticz user variables')
            self.saveUserVar()
        except:
            Domoticz.Error('Seems something with wrong with token response from spotify')

    def spotSearch(self, search_input, search_type):
        url = self.spotifyApiUrl + "/search?q={search_query}&type={search_type}&market=NL&limit=10".format(
            search_query=urllib.parse.quote(search_input), search_type=search_type)
        Domoticz.Debug('Spotify search url: ' + str(url))

        headers = self.spotGetBearerHeader()

        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req)

        jsonResponse = json.loads(response.read().decode('utf-8'))
        foundItems = jsonResponse['{}s'.format(search_type)]['items']

        Domoticz.Debug('First result of spotify search: ' + str(foundItems[0]))

        rsltString = 'Found ' + search_type + ' ' + foundItems[0]['name']
        if search_type == 'track':
            tracks = []
            for track in foundItems:
                tracks.append(track['uri'])
            returnData = {"uris": tracks}
        else:
            returnData = {"context_uri": foundItems[0]['uri']}

        if search_type == 'album' or search_type == 'track':
            rsltString += ' by ' + foundItems[0]['artists'][0]['name']

        Domoticz.Log(rsltString)
        return returnData

    def spotPause(self):
        try:
            url = self.spotifyApiUrl + "/me/player/pause"
            headers = self.spotGetBearerHeader()

            req = urllib.request.Request(url, headers=headers, method='PUT')
            response = urllib.request.urlopen(req)
            Domoticz.Log("Succesfully paused track")

        except urllib.error.HTTPError as err:
            if err.code == 403:
                Domoticz.Error("User non premium")
            elif err.code == 400:
                Domoticz.Error("Device id not found")
            else:
                Domoticz.Error("Unkown error, msg: " + str(err.msg))

    def spotCurrent(self):
        try:
            url = self.spotifyApiUrl + "/me/player"
            headers = self.spotGetBearerHeader()

            req = urllib.request.Request(url, headers=headers, method='GET')
            response = urllib.request.urlopen(req)

            Domoticz.Debug("Succesfully retrieved current playing state")
            Domoticz.Debug('Retrieved current playing state having code {}'.format(response.code))

            return response

        except urllib.error.HTTPError as err:
            Domoticz.Error("Unkown error {error}, msg: {message}".format(error=err.code, message=err.msg))

    def spotPlay(self, device_level_index=None, media_to_play=None):
        try:
            if device_level_index:
                if device_level_index not in self.spotArrDevices:
                    self.updateDeviceSelector()
                    if device_level_index not in self.spotArrDevices:
                        raise urllib.error.HTTPError(url='', msg='', hdrs='', fp='', code=404)

                device = self.spotArrDevices[device_level_index]
                url = self.spotifyApiUrl + "/me/player/play?device_id=" + device
            else:
                url = self.spotifyApiUrl + "/me/player/play"

            headers = self.spotGetBearerHeader()

            if media_to_play:
                data = json.dumps(media_to_play).encode('utf8')
                req = urllib.request.Request(url, headers=headers, data=data, method='PUT')
            else:
                req = urllib.request.Request(url, headers=headers, method='PUT')

            response = urllib.request.urlopen(req)
            if device_level_index:
                self.updateDomoticzDevice(SPOTIFYDEVICES, 1, str(device_level_index))
            Domoticz.Log("Succesfully started playback")

        except urllib.error.HTTPError as err:
            if err.code == 403:
                Domoticz.Error("Error playback, you need to be premium member")
            elif err.code == 400:
                Domoticz.Error("Error playback, right scope requested?")
            elif err.code == 404:
                Domoticz.Error("Device not found, went offline?")
            else:
                Domoticz.Error("Unkown error, msg: " + str(err.msg))

    def spotNext(self):
        try:
            url = self.spotifyApiUrl + "/me/player/next"
            headers = self.spotGetBearerHeader()

            req = urllib.request.Request(url, headers=headers, method='POST')
            response = urllib.request.urlopen(req)
            Domoticz.Log("Succesfully change to next track")

        except urllib.error.HTTPError as err:
            if err.code == 403:
                Domoticz.Error("User non premium")
            elif err.code == 400:
                Domoticz.Error("Device id not found")
            else:
                Domoticz.Error("Unkown error, msg: " + str(err.msg))

    def spotPrevious(self):
        try:
            url = self.spotifyApiUrl + "/me/player/previous"
            headers = self.spotGetBearerHeader()

            req = urllib.request.Request(url, headers=headers, method='POST')
            response = urllib.request.urlopen(req)
            Domoticz.Log("Succesfully change to previous track")

        except urllib.error.HTTPError as err:
            if err.code == 403:
                Domoticz.Error("Can't use previous option in this state - maybe radio or first song")
            elif err.code == 400:
                Domoticz.Error("Device id not found")
            else:
                Domoticz.Error("Unkown error, msg: " + str(err.msg))

    def onHeartbeat(self):
        if not self.blError:
            if Parameters["Mode5"] != "0" and self.heartbeatCounterPoll == int(Parameters["Mode5"]):
                Domoticz.Debug('Polling')
                response = self.spotCurrent()
                if response.code == 204 and Devices[SPOTIFYDEVICES].sValue != '0':
                    self.updateDomoticzDevice(SPOTIFYDEVICES, 0, "0")
                elif response.code == 200:
                    resultJson = json.loads(response.read().decode('utf-8'))

                    try:
                        if not resultJson['is_playing']:
                            self.updateDomoticzDevice(SPOTIFYDEVICES, 0, "0")
                        else:
                            lstSelectorLevel = catchDeviceSelectorLvl(resultJson['device']['name'])
                            self.updateDomoticzDevice(SPOTIFYDEVICES, 1, lstSelectorLevel)

                    except ValueError:
                        try:
                            Domoticz.Debug(
                                'Playing on device {device_name} which was unkown, trying to update domoticz device to '
                                'correctly update playback information.'.format(
                                    device_name=str(resultJson['device']['name'])))
                            self.updateDeviceSelector()
                            lstSelectorLevel = catchDeviceSelectorLvl(resultJson['device']['name'])
                            self.updateDomoticzDevice(SPOTIFYDEVICES, 1, lstSelectorLevel)
                        except ValueError:
                            Domoticz.Error("Current playing device not found by domoticz, cant update")

                    except UnicodeEncodeError:
                        # jsonresult is empty, meaning nothing is playing
                        self.updateDomoticzDevice(SPOTIFYDEVICES, 0, "0")

                self.heartbeatCounterPoll = 1
            else:
                self.heartbeatCounterPoll += 1

            return True

    def updateDomoticzDevice(self, idx, nValue, sValue):
        if Devices[idx].sValue != sValue or Devices[idx].nValue != nValue:
            Domoticz.Debug('Update for device {device_index} with nValue {device_value} and sValue {value_type}'.format(
                device_index=idx, device_value=nValue, value_type=sValue))
            Devices[idx].Update(nValue, sValue)

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug(
            "Spotify: onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(
                Level))
        Domoticz.Debug(
            "nValue={device_value}, sValue={value_type}".format(
                device_value=str(Devices[SPOTIFYDEVICES].nValue), value_type=str(Devices[SPOTIFYDEVICES].sValue)))
        Command = Command.strip()
        action, sep, params = Command.partition(' ')
        action = action.capitalize()

        if Unit == SPOTIFYDEVICES:
            try:
                variables = DomoticzAPI({'type': 'command', 'param': 'getuservariables'})
            except Exception as error:
                Domoticz.Error(error)

            if Level == 0:
                # Spotify turned off
                self.updateDomoticzDevice(Unit, 0, str(Level))
                self.spotPause()

            else:
                searchVariable = next(
                    (item for item in variables["result"] if item["Name"] == Parameters["Name"] + '-searchTxt'))
                searchString = searchVariable['Value']
                Domoticz.Log('Looking for ' + searchString)
                searchResult = None

                if searchString != "":
                    for type in ['artist', 'track', 'playlist', 'album']:
                        if type in searchString:
                            strippedSearch = searchString.replace(type, '').lstrip()
                            Domoticz.Debug('Search type: ' + type)
                            Domoticz.Debug('Search string: ' + strippedSearch)
                            searchResult = self.spotSearch(strippedSearch, type)
                            break

                if not searchResult:
                    Domoticz.Error(
                        "No correct type found in search string, use either artist, track, playlist or album")
                else:
                    self.spotPlay(str(Level), searchResult)

        elif Unit == SPOTIFYPLAYBACK:
            if (action == "On"):
                self.spotPlay()
                pass

            elif (action == "Set"):
                current_state_response = self.spotCurrent()
                current_state_json = json.loads(current_state_response.read().decode('utf-8'))
                is_playing = current_state_json['is_playing']
                if not is_playing:
                    self.spotPlay()
                if self.spotPlaybackSelectorMap[Level] == "Play":
                    if not is_playing:
                        self.spotPlay()
                    else:
                        Domoticz.Log("Spotify already playing")
                elif self.spotPlaybackSelectorMap[Level] == "Pause":
                    self.spotPause()
                elif self.spotPlaybackSelectorMap[Level] == "Next":
                    self.spotNext()
                elif self.spotPlaybackSelectorMap[Level] == "Previous":
                    self.spotPrevious()

            elif (action == "Off"):
                # Spotify turned off
                self.updateDomoticzDevice(Unit, 0, str(Level))
                self.spotPause()




_plugin = BasePlugin()


def onStart():
    _plugin.onStart()


def onHeartbeat():
    _plugin.onHeartbeat()


def onCommand(Unit, Command, Level, Hue):
    _plugin.onCommand(Unit, Command, Level, Hue)


#############################################################################
#                         Domoticz helper functions                         #
#############################################################################

def catchDeviceSelectorLvl(name):
    lstSelectorNames = Devices[SPOTIFYDEVICES].Options['LevelNames'].split('|')
    lstSelectorLevel = str(lstSelectorNames.index(name) * 10)
    return lstSelectorLevel


def DomoticzAPI(APICall):
    resultJson = None
    url = "http://{}:{}/json.htm?{}".format(Parameters["Address"], Parameters["Port"],
                                            urllib.parse.urlencode(APICall, safe="&="))
    Domoticz.Debug("Calling domoticz API: {}".format(url))
    try:
        req = urllib.request.Request(url)
        if Parameters["Username"] != "":
            Domoticz.Debug("Add authentification for user: {}".format(Parameters["Username"]))
            credentials = ('{username}:{password}'.format(
                username=Parameters["Username"], password=Parameters["Password"]))
            encoded_credentials = base64.b64encode(credentials.encode('ascii'))
            req.add_header('Authorization', 'Basic {}'.format(encoded_credentials.decode("ascii")))
        else:
            if Parameters["Mode4"] != "":
                Domoticz.Debug("Add authentification using encoded credentials: {}".format(Parameters["Mode4"]))
                encoded_credentials = Parameters["Mode4"]
                req.add_header('Authorization', 'Basic {}'.format(encoded_credentials))

        response = urllib.request.urlopen(req)

        if response.status == 200:
            resultJson = json.loads(response.read().decode('utf-8'))
            if resultJson["status"] != "OK":
                raise Exception("Domoticz API returned an error: status = {}".format(resultJson["status"]))
        else:
            raise Exception("Domoticz API: http error = {}".format(response.status))
    except:
        raise Exception("Error calling '{}'".format(url))

    return resultJson


#############################################################################
#                       Local test helpers                                  #
#############################################################################

if local:
    onStart()

    # onHeartbeat()

    # onCommand(1,'Off',0,'')
    onCommand(1, 'Set level', 20, '')
