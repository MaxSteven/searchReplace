# 
# Author: Fredrik Averpil, fredrik.averpil@gmail.com, http://fredrikaverpil.tumblr.com
# 

''' Imports regardless of Qt type '''
''' --------------------------------------------------------------------------------------------------------------------------------------------------------- '''
import os, sys
import xml.etree.ElementTree as xml
from cStringIO import StringIO	
import datetime, socket, fnmatch


''' CONFIGURATION '''
''' --------------------------------------------------------------------------------------------------------------------------------------------------------- '''

# General
QtType = 'PySide'										# Edit this to switch between PySide and PyQt
sys.dont_write_bytecode = True									# Do not generate .pyc files
uiFile = os.path.join(os.path.dirname(__file__), "searchReplace.ui")				# The .ui file to load
windowTitle = 'Search and Replace'									# The visible title of the window
windowObject = 'searchReplace'									# The name of the window object

# Standalone settings
darkorange = False										# Use the 'darkorange' stylesheet

# Maya settings
launchAsDockedWindow = False									# False = opens as free floating window, True = docks window to Maya UI

# Nuke settings
launchAsPanel = False										# False = opens as regular window, True = opens as panel

# Site-packages location:
site_packages_Win = ''										# Location of site-packages containing PySide and pysideuic and/or PyQt and SIP
site_packages_Linux = ''									# Location of site-packages containing PySide and pysideuic and/or PyQt and SIP
site_packages_OSX = ''										# Location of site-packages containing PySide and pysideuic and/or PyQt and SIP
#site_packages_Win = 'C:/Python26/Lib/site-packages'						# Example: Windows 7
#site_packages_Linux = '/usr/lib/python2.6/site-packages'					# Example: Linux CentOS 6.4
#site_packages_OSX = '/Library/Python/2.7/site-packages'					# Example: Mac OS X 10.8 Mountain Lion



''' Run mode '''
''' --------------------------------------------------------------------------------------------------------------------------------------------------------- '''
runMode = 'standalone'
try:
	import maya.cmds as cmds
	import maya.OpenMayaUI as omui
	import shiboken
	runMode = 'maya'
except:
	pass
try:
	import nuke
	from nukescripts import panels
	runMode = 'nuke'	
except:
	pass


''' PySide or PyQt '''
''' --------------------------------------------------------------------------------------------------------------------------------------------------------- '''
if (site_packages_Win != '') and ('win' in sys.platform): sys.path.append( site_packages_Win )
if (site_packages_Linux != '') and ('linux' in sys.platform): sys.path.append( site_packages_Linux )
if (site_packages_OSX != '') and ('darwin' in sys.platform): sys.path.append( site_packages_OSX )

if QtType == 'PySide':
	from PySide import QtCore, QtGui, QtUiTools
	import pysideuic	
elif QtType == 'PyQt':
	from PyQt4 import QtCore, QtGui, uic
	import sip
print 'This app is now using ' + QtType




''' Auto-setup classes and functions '''
''' --------------------------------------------------------------------------------------------------------------------------------------------------------- '''


class PyQtFixer(QtGui.QMainWindow):
	def __init__(self, parent=None):
		"""Super, loadUi, signal connections"""
		super(PyQtFixer, self).__init__(parent)
		print 'Making a detour (hack), necessary for when using PyQt'


def loadUiType(uiFile):
	"""
	Pyside lacks the "loadUiType" command, so we have to convert the ui file to py code in-memory first
	and then execute it in a special frame to retrieve the form_class.
	"""
	parsed = xml.parse(uiFile)
	widget_class = parsed.find('widget').get('class')
	form_class = parsed.find('class').text

	with open(uiFile, 'r') as f:
		o = StringIO()
		frame = {}

		if QtType == 'PySide':
			pysideuic.compileUi(f, o, indent=0)
			pyc = compile(o.getvalue(), '<string>', 'exec')
			exec pyc in frame

			#Fetch the base_class and form class based on their type in the xml from designer
			form_class = frame['Ui_%s'%form_class]
			base_class = eval('QtGui.%s'%widget_class)
		elif QtType == 'PyQt':
			form_class = PyQtFixer
			base_class = QtGui.QMainWindow
	return form_class, base_class
form, base = loadUiType(uiFile)



def wrapinstance(ptr, base=None):
	"""
	Utility to convert a pointer to a Qt class instance (PySide/PyQt compatible)

	:param ptr: Pointer to QObject in memory
	:type ptr: long or Swig instance
	:param base: (Optional) Base class to wrap with (Defaults to QObject, which should handle anything)
	:type base: QtGui.QWidget
	:return: QWidget or subclass instance
	:rtype: QtGui.QWidget
	"""
	if ptr is None:
		return None
	ptr = long(ptr) #Ensure type
	if globals().has_key('shiboken'):
		if base is None:
			qObj = shiboken.wrapInstance(long(ptr), QtCore.QObject)
			metaObj = qObj.metaObject()
			cls = metaObj.className()
			superCls = metaObj.superClass().className()
			if hasattr(QtGui, cls):
				base = getattr(QtGui, cls)
			elif hasattr(QtGui, superCls):
				base = getattr(QtGui, superCls)
			else:
				base = QtGui.QWidget
		return shiboken.wrapInstance(long(ptr), base)
	elif globals().has_key('sip'):
		base = QtCore.QObject
		return sip.wrapinstance(long(ptr), base)
	else:
		return None


def maya_main_window():
	main_window_ptr = omui.MQtUtil.mainWindow()
	return wrapinstance( long( main_window_ptr ), QtGui.QWidget )	# Works with both PyQt and PySide




''' Main class '''
''' --------------------------------------------------------------------------------------------------------------------------------------------------------- '''

class SearchReplace(form, base):
	def __init__(self, parent=None):
		"""Super, loadUi, signal connections"""
		super(SearchReplace, self).__init__(parent)

		if QtType == 'PySide':
			print 'Loading UI using PySide'
			self.setupUi(self)


		elif QtType == 'PyQt':
			print 'Loading UI using PyQt'
			uic.loadUi(uiFile, self)	

		self.setObjectName(windowObject)
		self.setWindowTitle(windowTitle)

		self.statusBar()
		self.statusBar().showMessage('I\'m ready for action')

		self.buttonTitleJustSearch = 'Just search'
		self.buttonTitleSearchReplace = 'Search and replace'
		self.buttonTitleStop = 'Stop'
		self.running = False
		self.abort = False

		#self.foundFiles = {}	 			# Main dictionary
		self.unCheckableFiles = []			# Store all files that we were unable to read

		self.lineEdit_startDir.setText( os.path.dirname(__file__) )
		

		self.pushButton_browse.clicked.connect( self.browseStartingDir ) # Click on browse button
		self.pushButton_find.clicked.connect( self.pushButtonJustSearch ) # Click on search button
		self.pushButton_replace.clicked.connect( self.pushButtonSearchReplace ) # Click on replace button
		

		self.listWidget_files.currentItemChanged.connect( self.showStrings ) # Click on filepath in listWidget



	def reset(self):
		print self.sender().text()
		# Change button to default value
		if self.sender().text() == self.buttonTitleStop:
			self.pushButton_find.setText( self.buttonTitleJustSearch )
			self.pushButton_replace.setText( self.buttonTitleSearchReplace )
			self.pushButton_replace.setEnabled(True)
			self.pushButton_find.setEnabled(True)
			
		


	def pushButtonJustSearch(self):
		if self.checkForErrorsJustSearch():
			pass
		else:
			sender = self.sender().text()
			self.pushButton_find.setText( self.buttonTitleStop )
			self.pushButton_replace.setEnabled(False)
			if sender == self.buttonTitleJustSearch:
				self.justSearch()
				self.reset()
				self.abort = False
			elif sender == self.buttonTitleStop:
				QtGui.QApplication.processEvents()
				self.abort = True
				QtGui.QApplication.processEvents()
				msg = 'User interrupt!'
				print msg
				self.log( msg )

		


	def pushButtonSearchReplace(self):
		if self.checkForErrorsJustSearch() or self.checkForErrorsSearchReplace():
			pass
		else:
			sender = self.sender().text()
			if sender == self.buttonTitleSearchReplace:
				
				# TO DO - ASK BEFORE!
				msg = 'Make sure you have made a backup of the directory you are running this script on!\n\nYou are about to start the search and replace process.\n\nContinue?'
				reply = QtGui.QMessageBox.question(self, 'Message', msg, QtGui.QMessageBox.Yes | QtGui.QMessageBox.No, QtGui.QMessageBox.No)
				if reply == QtGui.QMessageBox.Yes:
					self.pushButton_replace.setText( self.buttonTitleStop )
					self.pushButton_find.setEnabled(False)
					self.performReplace()
					self.reset()
					self.abort = False
			elif sender == self.buttonTitleStop:
				QtGui.QApplication.processEvents()
				self.abort = True
				QtGui.QApplication.processEvents()
				msg = 'User interrupt!'
				print msg
				self.log( msg )



	def checkForErrorsJustSearch(self):
		error = False

		if self.lineEdit_find.text() == '':
			self.statusBar().showMessage('Error: No search phrase!')
			error = True
		elif self.lineEdit_startDir.text() == '':
			self.statusBar().showMessage('Error: No start dir!')
			error = True
		elif not os.path.isdir( self.lineEdit_startDir.text() ):
			self.statusBar().showMessage('Error: Start dir does not exist!')
			error = True
		return error

	def checkForErrorsSearchReplace(self):
		error = False
		if self.lineEdit_replace.text() == '':
			self.statusBar().showMessage('Error: No replace phrase!')
			error = True
		return error


	def parseFiletypes(self, filetypesString):
		filetypesStringModified = filetypesString.replace(' ', '')	# Remove space
		filetypesList = filetypesStringModified.split(',') # Split to list on comma
		return filetypesList




	def preProcess(self): 
		# Create and clear lists and resets
		self.filesToSearch = []
		self.foundFiles = {}
		self.listWidget_files.clear()
		if self.lineEdit_filetypes.text() == '':
			self.lineEdit_filetypes.setText('*.*')
			QtGui.QApplication.processEvents()
		
		

		# Binary check inits
		textchars = ''.join(map(chr, [7,8,9,10,12,13,27] + range(0x20, 0x100)))
		is_binary_string = lambda bytes: bool(bytes.translate(None, textchars))

		# Starting directory
		startDirectory = self.lineEdit_startDir.text()

		# Status message		
		msg = 'Starting indexing of ' + startDirectory
		self.statusBar().showMessage( msg )
		self.log( msg )
		QtGui.QApplication.processEvents()
		

		# If filetype filter is active, make it clear which files to include
		filetypes = self.parseFiletypes( self.lineEdit_filetypes.text() )
		msg = 'Limiting search to filetypes ' + self.lineEdit_filetypes.text()
		self.log( msg )


		
		for root, dirs, files in os.walk( startDirectory ):

			if not self.abort:

				# Status message		
				msg = 'Indexing ' + root
				self.statusBar().showMessage( msg )
				QtGui.QApplication.processEvents()

				for extension in ( tuple(filetypes) ):

					for filename in fnmatch.filter(files, extension):

							filepath = os.path.join(root, filename)
							# Are we excluding binary files?
							if self.checkBox_skipBinary.isChecked():
								if os.path.isfile( filepath ):
									if is_binary_string(open( filepath ).read(1024)):
										# File is binary, do not do anything
										pass
									else:
										if not self.abort:
											self.filesToSearch.append( filepath )
							else:
								self.filesToSearch.append( filepath )

		# Status message		
		msg = 'Indexing completed'
		self.statusBar().showMessage( msg )
		self.log( msg )
		QtGui.QApplication.processEvents()
			

		fileCount = 1
		for filepath in self.filesToSearch:
			if not self.abort:
				self.statusBar().showMessage( 'Searching file (' + str(fileCount) + '/' + str(len(self.filesToSearch)) + '): ' + filepath )
				QtGui.QApplication.processEvents()									# Force update UI
				self.searchFile( filepath )
				fileCount += 1


		if len(self.unCheckableFiles) == 0:
			msg ='Done Searching ' + str(len(self.filesToSearch)) + ' files. Found ' + str(len( self.foundFiles.keys() )) + ' files with search phrase.'
			self.log( msg )
			self.statusBar().showMessage( msg )
		else:
			msg = 'Done Searching ' + str(len(self.filesToSearch)) + ' files. Found ' + str(len( self.foundFiles.keys() )) + ' files with search phrase, but some files could not be read (maybe they were open/locked or of certain unicode type).'
			self.log( msg )
			self.statusBar().showMessage( msg )



		



	def searchFile(self, filepath):
		if not self.abort:
			# Read contents of file
			with open(filepath, "r") as f:
				contents = f.read()

			searchString = str( self.lineEdit_find.text() )	# Get search string from UI

			# Add file to list if search string was found in file
			try:
				if searchString in contents:
					self.listWidget_files.addItem( filepath )						# Add file to listWidget
					QtGui.QApplication.processEvents()								# Force update UI
					
					lines = ''
					for line in contents.split('\n'):
							if searchString in line:
								lines += line + '\n'

					if not self.checkBox_noRecording.isChecked():
						self.foundFiles[ filepath ] = lines		# Create entry, record line
					else:
						self.foundFiles[ filepath ] = ''		# Create entry, do not record line


			except:
				self.unCheckableFiles.append( filepath )
				msg = 'Error: Unable to read ' + filepath
				self.log( msg )
				self.statusBar().showMessage( msg )







	def justSearch(self):
		if self.lineEdit_find.text() == '':
			self.statusBar().showMessage('Error: No search phrase!')
			return False
		elif self.lineEdit_startDir.text() == '':
			self.statusBar().showMessage('Error: No start dir!')
			return False
		elif not os.path.isdir( self.lineEdit_startDir.text() ):
			self.statusBar().showMessage('Error: Start dir does not exist!')
			return False
		else:
			msg = 'Start search for: ' + str(self.lineEdit_find.text()) + ' in ' + str(self.lineEdit_startDir.text())
			self.log( msg )
			self.preProcess()
			return True





	def performReplace(self):
		if self.lineEdit_replace.text() == '':
				self.statusBar().showMessage('Error: No replace phrase!')
		else:

			if self.justSearch():
				msg = 'Start replace with: ' + str(self.lineEdit_replace.text())
				self.log( msg )
				
				fileProcessedCount = 1
				for filepath in self.foundFiles.keys():

					if not self.abort:
						self.statusBar().showMessage('Reading (' + str(fileProcessedCount) + '/' + str(len( self.foundFiles.keys() )) + '): ' + filepath )
						QtGui.QApplication.processEvents()

						# Open the file as readable
						with open(filepath, 'r') as fr:
							originalContents = fr.read()

						if str(self.lineEdit_find.text()) in originalContents:
							newContents = originalContents.replace( str(self.lineEdit_find.text()) , str(self.lineEdit_replace.text()) )
							
							if not self.abort:
								with open(filepath, 'w') as fw:
									writtenFile = False
									try:
										self.statusBar().showMessage('Writing (' + str(fileProcessedCount) + '/' + str(len( self.foundFiles.keys() )) + '): ' + filepath )
										QtGui.QApplication.processEvents()
										fw.write(newContents)
										writtenFile = True
									except:
										msg = 'Error: unable to write ' + filepath
										self.log( msg )
										self.statusBar().showMessage( msg )
									# In the case where the file is locked or cannot be written - Attempt to write to a back up dump file
									if not writtenFile:
										try:
											dumpfilepath = filepath+'_DUMP'
											with open(dumpfilepath, 'w') as dumpfile:
												dumpfile.write(originalContents)
												msg = 'Dump file was written: ' + dumpfilepath
												self.log( msg )
												self.statusBar().showMessage( msg )
										except:
											msg = 'Severe error: Possible loss of data!'
											self.log( msg )
											self.statusBar().showMessage( msg )

						fileProcessedCount += 1


		msg = 'Done writing ' + str(fileProcessedCount-1) + ' files'
		self.log( msg )
		self.statusBar().showMessage( msg )


	def browseStartingDir(self):
		try:
			startingDir = os.path.dirname(__file__)
		except:
			startingDir = ''
		destDir = QtGui.QFileDialog.getExistingDirectory(None, 'Open working directory', startingDir, QtGui.QFileDialog.ShowDirsOnly)
		self.lineEdit_startDir.setText( destDir )
		


	def showStrings(self):
		self.listWidget_strings.clear()
	
		try:
			filepath = self.listWidget_files.currentItem().text()
			lines = self.foundFiles[ filepath ].split('\n')
			for line in lines:
				self.listWidget_strings.addItem( line )
		except:
			pass


	def log(self, message):
		timeStamp = str(datetime.datetime.now())
		with open( os.path.join( os.path.dirname(__file__), 'searchReplace.log'), 'a' ) as myfile:
			myfile.write( timeStamp + '\t\t' + str(socket.gethostname()) + '\t\t' + message + '\n')





''' Run functions '''
''' --------------------------------------------------------------------------------------------------------------------------------------------------------- '''

def runStandalone():
	app = QtGui.QApplication(sys.argv)
	global gui
	gui = SearchReplace()
	gui.show()

	if darkorange:
		themePath = os.path.join( os.path.dirname(__file__), 'theme' )
		sys.path.append( themePath )
		import darkorangeResource
		stylesheetFilepath = os.path.join( themePath, 'darkorange.stylesheet' )
		with open( stylesheetFilepath , 'r' ) as shfp:
			gui.setStyleSheet( shfp.read() )
		app.setStyle("plastique")
	
	sys.exit(app.exec_())

def runMaya():
	if cmds.window(windowObject, q=True, exists=True):
		cmds.deleteUI(windowObject)
	global gui
	gui = SearchReplace( maya_main_window() )

	if launchAsDockedWindow:
		allowedAreas = ['right', 'left']
		cmds.dockControl( label=windowTitle, area='left', content=windowObject, allowedArea=allowedAreas )
	else:
		gui.show() 

def runNuke():
	moduleName = __name__
	if moduleName == '__main__':
		moduleName = ''
	else:
		moduleName = moduleName + '.'
	global gui
	if launchAsPanel:
		pane = nuke.getPaneFor('Properties.1')
		panel = panels.registerWidgetAsPanel( moduleName + 'SearchReplace' , windowTitle, ('uk.co.thefoundry.'+windowObject+'Window'), True).addToPane(pane) # View pane and add it to panes menu
		gui = panel.customKnob.getObject().widget
	else:
		gui = SearchReplace()
		gui.show()





if runMode == 'standalone':
	runStandalone()
'''
elif runMode == 'maya':
	runMaya()
elif runMode == 'nuke':
	runNuke()
'''
