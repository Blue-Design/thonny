# -*- coding: utf-8 -*-

import sys
import webbrowser
import platform

import tkinter as tk
from tkinter import ttk
import tkinter.font as font

from thonny import misc_utils
import thonny.user_logging

#TODO - consider moving the cmd_find method to main class in order to pass the editornotebook reference
#TODO - logging
#TODO - instead of text.see method create another one which attempts to center the line where the text was found
#TODO - test on mac and linux

# Handles the find dialog display and the logic of searching.
#Communicates with the codeview that is passed to the constructor as a parameter.
class FindDialog(tk.Toplevel): 
    def __init__(self, parent): #constructor
        tk.Toplevel.__init__(self, parent, borderwidth=15, takefocus=1) #superclass constructor
        thonny.user_logging.log_user_event(FindWindowOpenEvent(parent.master))
        self.codeview = parent; 
        self._init_found_tag_styles();  #sets up the styles used to highlight found strings
        #references to the current set of passive found tags e.g. all words that match the searched term but are not the active string
        self.passive_found_tags = set()
        self.active_found_tag = None    #reference to the currently active (centered) found string

        #if find dialog was used earlier then put the previous search word to the Find entry field
        #TODO - refactor this, there must be a better way
        try:
            #if find dialog was used earlier then this is present
            FindDialog.last_searched_word = FindDialog.last_searched_word
        except:
            FindDialog.last_searched_word = None #if this variable does not exist then this is the first time find dialog has been launched

        #a tuple containing the start and indexes of the last processed string
        #if the last action was find, then the end index is start index + 1
        #if the last action was replace, then the indexes correspond to the start
        #and end of the inserted word
        self.last_processed_indexes = None
        self.last_search_case = None    #case sensitivity value used during the last search
        
        #set up window display
        self.geometry("+%d+%d" % (parent.winfo_rootx() + parent.winfo_width() // 2,
                                  parent.winfo_rooty() + parent.winfo_height() // 2 - 150))

        self.title("Find & Replace")
        if misc_utils.running_on_mac_os():
            self.configure(background="systemSheetBackground")
        self.resizable(height=tk.FALSE, width=tk.FALSE)
        self.transient(parent) 
        self.grab_set()        
        self.protocol("WM_DELETE_WINDOW", self._ok)
      
        #Find text label
        self.find_label = ttk.Label(self, text="Find:");    #TODO - text to resources package
        self.find_label.grid(column=0, row=0);

        #Find text field
        self.find_entry_var = tk.StringVar()
        self.find_entry = ttk.Entry(self, textvariable=self.find_entry_var);
        self.find_entry.grid(column=1, row=0, columnspan=2, padx=5);
        if FindDialog.last_searched_word != None:
            self.find_entry.insert(0, FindDialog.last_searched_word)
        self.find_entry.focus_force();

        #Replace text label
        self.replace_label = ttk.Label(self, text="Replace with:");    #TODO - text to resources package
        self.replace_label.grid(column=0, row=1);

        #Replace text field
        self.replace_entry = ttk.Entry(self);
        self.replace_entry.grid(column=1, row=1, columnspan=2, padx=5);

        #Info text label (invisible by default, used to tell user that searched string was not found etc)
        self.infotext_label_var = tk.StringVar();
        self.infotext_label_var.set("");
        self.infotext_label = ttk.Label(self, textvariable=self.infotext_label_var, foreground="red"); #TODO - style to conf
        self.infotext_label.grid(column=0, row=2, columnspan=3,pady=3);

        #Case checkbox
        self.case_var = tk.IntVar()
        self.case_checkbutton = ttk.Checkbutton(self,text="Case sensitive",variable=self.case_var);  #TODO - text to resources
        self.case_checkbutton.grid(column=0, row=3)

        #Direction radiobuttons
        self.direction_var = tk.IntVar()
        self.up_radiobutton = ttk.Radiobutton(self, text="Up", variable=self.direction_var, value=1)
        self.up_radiobutton.grid(column=1, row=3)
        self.down_radiobutton = ttk.Radiobutton(self, text="Down", variable=self.direction_var, value=2)
        self.down_radiobutton.grid(column=2, row=3)
        self.down_radiobutton.invoke()

        #Find button - goes to the next occurrence
        self.find_button = ttk.Button(self, text="Find", command=self._perform_find) #TODO - text to resources
        self.find_button.grid(column=3, row=0, sticky=tk.W + tk.E);
        self.find_button.config(state='disabled') 

        #Replace button - replaces the current occurrence, if it exists
        self.replace_button = ttk.Button(self, text="Replace", command=self._perform_replace) #TODO - text to resources
        self.replace_button.grid(column=3, row=1, sticky=tk.W + tk.E);
        self.replace_button.config(state='disabled')

        #Replace + find button - replaces the current occurence and goes to next
        self.replace_and_find_button = ttk.Button(self, text="Replace+Find", command=self._perform_replace_and_find) #TODO - text to resources
        self.replace_and_find_button.grid(column=3, row=2, sticky=tk.W + tk.E);
        self.replace_and_find_button.config(state='disabled')  
 
        #Replace all button - replaces all occurrences
        self.replace_all_button = ttk.Button(self, text="Replace all", command=self._perform_replace_all) #TODO - text to resources
        self.replace_all_button.grid(column=3, row=3, sticky=tk.W + tk.E);        
        if FindDialog.last_searched_word == None:
            self.replace_all_button.config(state='disabled') 

        #create bindings
        self.bind('<Escape>', self._ok)
        self.find_entry.bind('<Return>', self._perform_find)
        self.find_entry.bind('<Return>', self._perform_find)
        self.find_entry_var.trace('w', self._update_button_statuses)

        self._update_button_statuses()

        self.wait_window()

    #callback for text modifications on the find entry object, used to dynamically enable and disable buttons
    def _update_button_statuses(self, *args):
        find_text = self.find_entry_var.get().strip()
        if len(find_text) == 0:
            self.find_button.config(state='disabled')
            self.replace_and_find_button.config(state='disabled')
            self.replace_all_button.config(state='disabled')
        else:
            self.find_button.config(state='normal')
            self.replace_all_button.config(state='normal')
            if self.active_found_tag != None: 
                self.replace_and_find_button.config(state='normal')

    #returns whether the next search is case sensitive based on the current value of the case sensitivity checkbox
    def _is_search_case_sensitive(self):
        return self.case_var.get() != 0

    #returns whether the current search is a repeat of the last searched based on all significant values
    def _repeats_last_search(self, tofind):
        return tofind == FindDialog.last_searched_word and self.last_processed_indexes != None and self.last_search_case == self._is_search_case_sensitive();


    #performs the replace operation - replaces the currently active found word with what is entered in the replace field
    def _perform_replace(self, event=None, log=True):

        #nothing is currently in found status
        if self.active_found_tag == None:
            return

        #get the found word bounds
        del_start = self.active_found_tag[0]
        del_end = self.active_found_tag[1]

        #erase all tags - these would not be correct anyway after new word is inserted
        self._remove_all_tags()
        toreplace = self.replace_entry.get().strip(); #get the text to replace

        thonny.user_logging.log_user_event(ReplaceEvent(self.codeview.text.get(del_start, del_end), toreplace))
        #delete the found word
        self.codeview.text.delete(del_start, del_end)
        #insert the new word
        self.codeview._user_text_insert(del_start, toreplace)
        #mark the inserted word boundaries 
        self.last_processed_indexes = (del_start, self.codeview.text.index("%s+%dc" % (del_start, len(toreplace))))

    #performs the replace operation followed by a new find
    def _perform_replace_and_find(self, event=None):
        if self.active_found_tag == None:
            return
        self._perform_replace()
        self._perform_find()

    #replaces all occurences of the search string with the replace string
    def _perform_replace_all(self, event=None):

        tofind = self.find_entry.get().strip();
        if len(tofind) == 0:
            self.infotext_label_var.set("Enter string to be replaced.")
            return
        
        toreplace = self.replace_entry.get().strip();
   
        self._remove_all_tags()

        currentpos = 1.0;
        end = self.codeview.text.index("end");

        thonny.user_logging.log_user_event(ReplaceAllEvent(tofind, toreplace))

        while True:
            currentpos = self.codeview.text.search(tofind, currentpos, end, nocase = not self._is_search_case_sensitive()); 
            if currentpos == "":
                break

            endpos = self.codeview.text.index("%s+%dc" % (currentpos, len(tofind)))

            self.codeview.text.delete(currentpos, endpos)

            if toreplace != "":
                self.codeview._user_text_insert(currentpos, toreplace)
                
            currentpos = self.codeview.text.index("%s+%dc" % (currentpos, len(toreplace)))

    #performs the find action
    def _perform_find(self, event=None, log=True):
        self.infotext_label_var.set("");    #reset the info label text
        tofind = self.find_entry.get().strip(); #get the text to find 
        if len(tofind) == 0:    #in the case of empty string, cancel
            return              #TODO - set warning text to info label?

        search_backwards = self.direction_var.get() == 1 #True - search backwards ('up'), False - forwards ('down')
        
        if self._repeats_last_search(tofind): #continuing previous search, find the next occurrence
            if search_backwards:
                search_start_index = self.last_processed_indexes[0];
            else:
                search_start_index = self.last_processed_indexes[1];
            
            if self.active_found_tag != None:
                self.codeview.text.tag_remove("currentfound", self.active_found_tag[0], self.active_found_tag[1]);  #remove the active tag from the previously found string
                self.passive_found_tags.add((self.active_found_tag[0], self.active_found_tag[1]))                   #..and set it to passive instead
                self.codeview.text.tag_add("found", self.active_found_tag[0], self.active_found_tag[1]);
        
        else: #start a new search, start from the current insert line position
            if self.active_found_tag != None:
                self.codeview.text.tag_remove("currentfound", self.active_found_tag[0], self.active_found_tag[1]); #remove the previous active tag if it was present
            for tag in self.passive_found_tags:
                self.codeview.text.tag_remove("found", tag[0], tag[1]);                                            #and remove all the previous passive tags that were present
            search_start_index = self.codeview.text.index("insert");    #start searching from the current insert position
            self._find_and_tag_all(tofind);                             #set the passive tag to ALL found occurences
            FindDialog.last_searched_word = tofind;                     #set the data about last search
            self.last_search_case = self._is_search_case_sensitive();       

        
        if log: 
            thonny.user_logging.log_user_event(FindEvent(tofind, 'backwards' if search_backwards else 'forwards', 'case sensitive' if self._is_search_case_sensitive() else 'not case sensitive'))
        wordstart = self.codeview.text.search(tofind, search_start_index, backwards = search_backwards, forwards = not search_backwards, nocase = not self._is_search_case_sensitive()); #performs the search and sets the start index of the found string
        if len(wordstart) == 0:
            self.infotext_label_var.set("The inserted string can't be found!"); #TODO - better text, also move it to the texts resources list
            self.replace_and_find_button.config(state='disabled')
            self.replace_button.config(state='disabled')            
            return
        
        self.last_processed_indexes = (wordstart, self.codeview.text.index("%s+1c" % wordstart)); #sets the data about last search      
        self.codeview.text.see(wordstart); #moves the view to the found index
        wordend = self.codeview.text.index("%s+%dc" % (wordstart, len(tofind))); #calculates the end index of the found string
        self.codeview.text.tag_add("currentfound", wordstart, wordend); #tags the found word as active
        self.active_found_tag = (wordstart, wordend);
        self.replace_and_find_button.config(state='normal')
        self.replace_button.config(state='normal')

    #called when the window is closed. responsible for handling all cleanup. 
    def _ok(self, event=None):
        thonny.user_logging.log_user_event(FindWindowCloseEvent(self.codeview.master))
        self._remove_all_tags()
        self.destroy()

    #removes the active tag and all passive tags
    def _remove_all_tags(self):
        for tag in self.passive_found_tags:
            self.codeview.text.tag_remove("found", tag[0], tag[1]); #removes the passive tags

        if self.active_found_tag != None:
            self.codeview.text.tag_remove("currentfound", self.active_found_tag[0], self.active_found_tag[1]); #removes the currently active tag   

        self.active_found_tag = None
        self.replace_and_find_button.config(state='disabled')
        self.replace_button.config(state='disabled')        
        
    #finds and tags all occurences of the searched term
    def _find_and_tag_all(self, tofind, force=False): 
        #TODO - to be improved so only whole words are matched - surrounded by whitespace, parentheses, brackets, colons, semicolons, points, plus, minus

        if self._repeats_last_search(tofind) and not force:   #nothing to do, all passive tags already set
            return

        currentpos = 1.0;
        end = self.codeview.text.index("end");

        #searches and tags until the end of codeview
        while True:
            currentpos = self.codeview.text.search(tofind, currentpos, end, nocase = not self._is_search_case_sensitive()); 
            if currentpos == "":
                break

            endpos = self.codeview.text.index("%s+%dc" % (currentpos, len(tofind)))
            self.passive_found_tags.add((currentpos, endpos))
            self.codeview.text.tag_add("found", currentpos, endpos);
            
            currentpos = self.codeview.text.index("%s+1c" % currentpos);

    #initializes the tagging styles 
    def _init_found_tag_styles(self):
        self.codeview.text.tag_configure("found", foreground="green", underline=True) #TODO - style
        self.codeview.text.tag_configure("currentfound", foreground="white", background="red")  #TODO - style


class FindWindowOpenEvent(thonny.user_logging.UserEvent):
    def __init__(self, editor):
        self.editor_id = id(editor)

class FindWindowCloseEvent(thonny.user_logging.UserEvent):
    def __init__(self, editor):
        self.editor_id = id(editor)

class FindEvent(thonny.user_logging.UserEvent):
    def __init__(self, text, direction, case_sensitivity):
        self.text = text
        self.direction = direction
        self.case_sensitivity = case_sensitivity

class ReplaceEvent(thonny.user_logging.UserEvent):
    def __init__(self, previous_text, new_text):
        self.previous_text = previous_text
        self.new_text = new_text

class ReplaceAllEvent(thonny.user_logging.UserEvent):
    def __init__(self, previous_text, new_text):
        self.previous_text = previous_text
        self.new_text = new_text