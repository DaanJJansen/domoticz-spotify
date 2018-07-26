# Domoticz Spotify
Python plugin for Domoticz: Control spotify using domoticz 
See http://www.domoticz.com for more information on the platform.  
Discussion thread about this plugin: http://www.domoticz.com/forum/viewtopic.php?f=65&t=24020

## Requirements:
* Spotify premium account
* Domoticz with python plugin framework enabled
* Python3.5 or higher

## Installation:
* > cd ~/domoticz/plugins
* > git clone https://github.com/DaanJJansen/domoticz-spotify spotify (or any other target directory you like)
* You should now have a ~/domoticz/plugins/spotify directory that contains the plugin.py. In the future you can update the plugin by going into this directory and do a 'git pull'.
* Restart Domoticz
* Add the plugin in the Domoticz hardware configuration screen
* Create a client ID at spotify (https://developer.spotify.com/dashboard/applications)
	* Enter all fields as desired
	* Enter IP address on which domoticz can be reached
	* Entered port nr on which domoticz can be reached
	* Enter just created client id and client secret into hardware parameters
	* Go to 'edit setting' and 'http://localhost' as redirect URI
	* In your webbrowser, navigate to this url: https://accounts.spotify.com/authorize?client_id=[YOURCLIENT_ID]&redirect_uri=http://localhost&response_type=code&scope=user-read-playback-state+user-modify-playback-state
	* If all go's well, you are being redirect to localhost returning a 404, with a code in the query parameters, copy this code into the hardware parameters
	* Polling: poll spotify api for current playback state, update domoticz device accordingly
* Add hardware
* Add newly created Spotify-device from your device tab

## Usage:
* Update user variable [name]-searchTxt with the query parameter by using the type of search and the search string. The following types could be used:
	* artist -> find artist, eg searchTxt: 'artist coldplay' This will play the top tracks of Coldplay
	* track --> find song, eg searchTxt: 'track song 2'. Will play 10 tracks which matches with your search string
	* album --> find album, eg searchTxt: 'album Ten'. Will play album 10 by Pearl Jam
	* playlist --> find playlist, eg searchTxt: 'playlist discover weekly'. Will play the complete playlist for you.
* On the spotify-device select device on which playback needs to be started

## History:
**version 0.2**
- Fixed bug of not updating domoticz selector device
- Add Off/Pause functionality
- Added a new polling interval to update domoticz device in case spotify player updated via other system
- Removed parameter refresh interval spotify devices, will be updated in case playback is started on an unkown device
- Fixed bug of unwanted updated of domoticz variable search string

**version 0.11**
- Added additional logging for debugging purposes
- Fixed bug in case no user variables exists on Domoticz

**version 0.1**
- Initial setup