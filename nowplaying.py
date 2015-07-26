# -*- Mode: python; coding: utf-8; tab-width: 8; indent-tabs-mode: t; -*-
# vim: expandtab shiftwidth=8 softtabstop=8 tabstop=8

import os

import rb, operator
from gi.repository import RB
from gi.repository import GObject, Peas, Gtk, Gio, GdkPixbuf

#FIXME: Move this to a .ui file
ui_context_menus = """ 
<interface>
  <menu id="NP-source-popup">
    <submenu>
      <attribute name="label" translatable="yes">Remove</attribute>
      <section>
        <item>
      	  <attribute name="label" translatable="yes">Song</attribute>
	  <attribute name="action">app.clipboard-delete</attribute>
        </item>
        <item>
      	  <attribute name="label" translatable="yes">Album</attribute>
	  <attribute name="action">app.NP-source-delete-album</attribute>
        </item>
        <item>
      	  <attribute name="label" translatable="yes">Artist</attribute>
	  <attribute name="action">app.NP-source-delete-artist</attribute>
        </item>
      </section>
    </submenu>
    <section>
      <attribute name="rb-plugin-menu-link">source-popup</attribute>
    </section>
    <section>
      <item>
	<attribute name="label" translatable="yes">Pr_operties</attribute>
	<attribute name="action">app.clipboard-properties</attribute>
      </item>
    </section>
  </menu>
  <menu id="NP-sidebar-popup">
    <submenu>
      <attribute name="label" translatable="yes">Remove</attribute>
      <section>
        <item>
      	  <attribute name="label" translatable="yes">Song</attribute>
	  <attribute name="action">app.NP-sidebar-delete-song</attribute>
        </item>
        <item>
      	  <attribute name="label" translatable="yes">Album</attribute>
	  <attribute name="action">app.NP-sidebar-delete-album</attribute>
        </item>
        <item>
      	  <attribute name="label" translatable="yes">Artist</attribute>
	  <attribute name="action">app.NP-sidebar-delete-artist</attribute>
        </item>
      </section>
    </submenu>
    <section>
      <attribute name="rb-plugin-menu-link">sidebar-popup</attribute>
    </section>
    <section>
      <item>
	<attribute name="label" translatable="yes">Pr_operties</attribute>
	<attribute name="action">app.sidebar-properties</attribute>
      </item>
    </section>
  </menu>
</interface>
"""

class NowPlayingSource(RB.StaticPlaylistSource):
        def __init__(self):
                super(NowPlayingSource,self).__init__()
                self.__activated = False
                self.__playing_source = None
                self.__signals = None

        def do_activate(self):
                if self.__activated:
                        print("SOURCE ALREADY ACTIVATED!")
                        return

                print("ACTIVATING SOURCE!")
                self.__activated = True
                self.__entry_view = self.get_entry_view()
                self.__playing_source = None
                self.create_sidebar()

                app = Gio.Application.get_default()
                # Create action to add items to Now Playing
                browser_action = Gio.SimpleAction(name="add-to-now-playing")
                browser_action.connect("activate", self.add_entries_callback)
                app.add_action(browser_action)
                # Add the corresponding menu item to the library
                item = Gio.MenuItem()
                item.set_label("Add to Now Playing")
                item.set_detailed_action("app.add-to-now-playing")
                app.add_plugin_menu_item('browser-popup', 
                                        'add-to-now-playing', item)

                # Create the sidebar context menu actions
                action = Gio.SimpleAction(name="NP-sidebar-delete-song")
                action.connect("activate", 
                        self.menu_delete_entry_callback, 
                        RB.RhythmDBPropType.TITLE, self.__sidebar)
                app.add_action(action)
                action = Gio.SimpleAction(name="NP-sidebar-delete-album")
                action.connect("activate", 
                        self.menu_delete_entry_callback,
                        RB.RhythmDBPropType.ALBUM, self.__sidebar)
                app.add_action(action)
                action = Gio.SimpleAction(name="NP-sidebar-delete-artist")
                action.connect("activate", 
                        self.menu_delete_entry_callback, 
                        RB.RhythmDBPropType.ARTIST, self.__sidebar)
                app.add_action(action)
                prop_action = Gio.SimpleAction(name="sidebar-properties")
                prop_action.connect("activate", 
                        self.sidebar_properties_callback)
                app.add_action(prop_action)
                # ...and the source page context menu actions
                action = Gio.SimpleAction(name="NP-source-delete-album")
                action.connect("activate", 
                        self.menu_delete_entry_callback,
                        RB.RhythmDBPropType.ALBUM, self.__entry_view)
                app.add_action(action)
                action = Gio.SimpleAction(name="NP-source-delete-artist")
                action.connect("activate", 
                        self.menu_delete_entry_callback, 
                        RB.RhythmDBPropType.ARTIST, self.__entry_view)
                app.add_action(action)

                # Create the context menus from XML
                builder = Gtk.Builder.new_from_string(ui_context_menus,
                        len(ui_context_menus))
                self.__source_menu = builder.get_object("NP-source-popup")
                self.__sidebar_menu = builder.get_object("NP-sidebar-popup")

                # Connect to row-inserted and row-deleted signals from Now 
                # Playing QueryModel. We catch this signal to update the song 
                # count on the titles of the source page and sidebar.
                signals = self.__signals = []
                query_model = self.get_property("base-query-model")
                signals.append((query_model.connect("row-inserted",
                                        self.row_inserted_callback),
                                query_model))
                                
                signals.append((query_model.connect("row-deleted", 
                                        self.row_deleted_callback),
                                query_model))

                # Connect to ShellPlayer's "playing-source-changed"...
                shell = self.get_property("shell")
                shell_player = shell.get_property("shell-player")
                signals.append((shell_player.connect(
                                        "playing-source-changed",
                                        self.source_changed_callback),
                                shell_player))
                # ... and "playing-changed". XXX: I prob. should connect to
                # this signal only after activating the source
                signals.append((shell_player.connect("playing-changed",
                                        self.playing_changed_callback),
                                shell_player))

                # Activating Now Playing. FIXME: This should be smoother
                playing_source = shell_player.get_playing_source()
                if playing_source:
                        shell_player.stop()
                        shell_player.set_playing_source(playing_source)
                        shell_player.stop()
                                

        def do_delete_thyself(self):
                if not self.__activated:
                        print("SOURCE IS NOT ACTIVATED!")
                        return

                print("DEACTIVATING")
                # Remove menu action
                shell = self.get_property("shell")
                app = Gio.Application.get_default()
                app.remove_action('add-to-now-playing')
                app.remove_plugin_menu_item('browser-popup', 'add-to-now-playing')

                # Disconnect from signals
                for signal_id, signal_emitter in self.__signals:
                        signal_emitter.disconnect(signal_id)
                del self.__signals

                # Get the current playing status to use later
                shell = self.get_property("shell")
                player = shell.get_property("shell-player")
                ret, playing = player.get_playing()
                playing_entry = player.get_playing_entry()

                # Clear query model
                query_model = self.get_property("base-query-model")
                iter = query_model.get_iter_first() 
                #FIXME: Isn't there an API call to clear the model?
                for treerow in query_model:     # Clear current selection
                        entry, path = list(treerow)
                        self.remove_entry(entry)

                self.get_property("shell").remove_widget (
                        self.__sidebar, RB.ShellUILocation.RIGHT_SIDEBAR)
                # Set the new source and playing entry
                # XXX: Maybe I should just stop playback and scroll to the
                # previously playing entry
                if self.__playing_source:
                        if ret and playing and playing_entry:
                                player.play_entry(playing_entry, 
                                        self.__playing_source)

                # Remove display page
                shell.get_property("display-page-model").remove_page(self)

                del self.__playing_source

        def do_impl_can_rename(self):
                return False

        # Callback for the delete actions of the context menus of both the 
        # sidebar and the source page. Deletes from 'view' all the entries 
        # with property 'prop'.
        def menu_delete_entry_callback(self, action, data, prop, view):
                selected_entries = view.get_selected_entries()
                if prop == RB.RhythmDBPropType.TITLE:
                        for entry in selected_entries:
                                self.remove_entry(entry)
                        return
                model = self.get_property("base-query-model")
                delete_keys = set()
                for entry in selected_entries:
                        delete_keys.add(entry.get_string(prop))
                entries_to_delete = set()
                model.foreach(self.delete_entry_by_prop, 
                          prop, delete_keys, entries_to_delete)
                for entry in entries_to_delete:
                          self.remove_entry(entry)
                del delete_keys
                del entries_to_delete


        # Used by 'menu_delete_entry_callback'. Deletes and entry
        # (given by 'iter') if the value of its 'prop' property
        # is in 'prop_set'.
        def delete_entry_by_prop(self, model, path, iter, prop, 
                        prop_set, entries_to_delete):
                entry = model.iter_to_entry(iter)
                entry_prop = entry.get_string(prop)
                if(entry_prop in prop_set):
                        entries_to_delete.add(entry)
                return False

        # Callback for the 'Properties' action of the sidebar's context menu.
        def sidebar_properties_callback(self, action, data):
                song_info = RB.SongInfo.new(self, self.__sidebar)
                song_info.show_all()

        def do_impl_show_entry_view_popup(self, view, over_entry):
                if view == self.__sidebar:
                        menu = Gtk.Menu.new_from_model(self.__sidebar_menu)
                else:
                        menu = Gtk.Menu.new_from_model(self.__source_menu)
                menu.attach_to_widget(self, None)
                menu.popup(None, None, None, None, 3, Gtk.get_current_event_time())

        def create_sidebar(self):
                shell = self.get_property("shell")
                sidebar = self.__sidebar = RB.EntryView.new(
                        shell.get_property("db"), 
                        shell.get_property("shell-player"), 
                        True, True)

                sidebar.set_property("vscrollbar-policy", Gtk.PolicyType.AUTOMATIC)
                sidebar.set_property("shadow-type", Gtk.ShadowType.NONE)
                sidebar.get_style_context().add_class("nowplaying-sidebar")

                renderer = Gtk.CellRendererText.new()
                sidebar_column = self.__sidebar_column = Gtk.TreeViewColumn.new()
                sidebar_column.pack_start(renderer, True)
                sidebar_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
                sidebar_column.set_expand(True)
                sidebar_column.set_clickable(False)

                sidebar_column.set_cell_data_func(renderer, self.cell_data_func)
        
                sidebar.append_column_custom(
                        sidebar_column, _("Now Playing"), 
                        "Title", operator.gt, None)
                sidebar.set_columns_clickable(False)
                super(NowPlayingSource,self).setup_entry_view(sidebar)
                query_model = self.get_property("query-model")
                sidebar.set_model(query_model)
                self.get_property("shell").add_widget (
                        sidebar, RB.ShellUILocation.RIGHT_SIDEBAR, True, True)
                sidebar.set_visible(True)
                sidebar.show_all()

	        # Connect to the "entry-activated" signal of the sidebar
                sidebar.connect("entry-activated", 
                        self.sidebar_entry_activated_callback)

        def cell_data_func(self, sidebar_column, renderer, tree_model, iter, data):
                db = self.get_property("shell").get_property("db")
                entry = tree_model.get(iter, 0)[0]
                title = entry.get_string(RB.RhythmDBPropType.TITLE)
                artist = entry.get_string(RB.RhythmDBPropType.ARTIST)
                album = entry.get_string(RB.RhythmDBPropType.ALBUM)
                markup = "<span size=\"smaller\">" + \
                        "<b>" + GObject.markup_escape_text(title) + "</b>\n" + \
                        "<i>" + GObject.markup_escape_text(album) + "</i>\n" + \
                        "<i>" + GObject.markup_escape_text(artist) + "</i></span>"
                renderer.set_property("markup", markup)

        def sidebar_entry_activated_callback(self, sidebar, selected_entry):
                player = self.get_property("shell").get_property("shell-player")
                player.play_entry(selected_entry, self)

        #####################################################################
        #                       CALLBACKS                                   #
        #####################################################################
        # Callback to the "row_inserted" signal to RBEntryView.
        # Updates the song number shown in brackets in the display tree.
        def row_inserted_callback(self, model, tree_path, iter):
                name = base_name = _("Now Playing")
                count = model.iter_n_children(None)
                if count > 0:
                        name = base_name + " (" + str(count) + ")"
                self.set_property("name", name)
                self.__sidebar_column.set_title(name)

        # Callback to the "row_inserted" signal to RBEntryView.
        # Updates the song number shown in brackets in the display tree.
        def row_deleted_callback(self, model, tree_path):
                count = model.iter_n_children(None)
                name = base_name = _("Now Playing")
                if count -1 > 0:
                        name = base_name + " (" + str(count - 1) + ")"
                self.set_property("name", name)
                self.__sidebar_column.set_title(name)
        
        # Updates the playing status symbol (play/pause) next to the playing
        # entry in the NowPlaying source. 
        def playing_changed_callback(self, player, playing):
                print("PLAY STATE CHANGED!")
                if not self.__playing_source:
                        return
                entry_view = self.__entry_view
                sidebar = self.__sidebar
                state = None
                if playing:
                        state = RB.EntryViewState.PLAYING
                else:
                        state = RB.EntryViewState.PAUSED
                # Update the playing symbol EVERYWHERE
                entry_view.set_state(state)
                sidebar.set_state(state)
                self.__playing_source.get_entry_view().set_state(state)

                # Scroll to playing entry if it is not visible
                playing_entry = player.get_playing_entry()
                if playing_entry:
                        entry_view.scroll_to_entry(playing_entry)
                        sidebar.scroll_to_entry(playing_entry)
        
        # When a source is selected to play, we intercept that call and replace
        # the selected source with the NowPlayingSource.
        # XXX: Replacing is not the most efficient/elegant solution...
        def source_changed_callback(self, player, new_source):
                if new_source == None:
                        print("NO SOURCE SELECTED")
                        self.__playing_source = None
                        return

                print("NEW SOURCE PLAYING: " + new_source.get_property("name"))

                if new_source == self:
                        print("IT'S US!!")
                        return

                # XXX: What if they are the same?
                if self.__playing_source == new_source:
                        print("SAME SOURCE, DOESNT COUNT")
                self.__playing_source = new_source
                playing_source_view = new_source.get_entry_view()
                
                # FIXME: Should I be using base_query_model instead?
                # Clear current selection
                query_model = self.get_property("query-model")
                for treerow in query_model:
                        entry, path = list(treerow)
                        self.remove_entry(entry)
                # Add new entries
                new_source_model = new_source.get_property("query-model")
                for treerow in new_source_model:
                        entry, path = list(treerow)
                        self.add_entry(entry, -1)
                player.set_playing_source(self)
                playing_source_view.set_state(RB.EntryViewState.PLAYING)


        # Callback for the 'Add to Now Playing' action we added to the 
        # context menu of the library browser.
        def add_entries_callback(self, action, data):
                shell = self.get_property("shell")
                library_source = self.shell.get_property("library-source")
                selected = library_source.get_entry_view().get_selected_entries()
                for selected_entry in selected:
                        self.add_entry(selected_entry, -1)
                return


class NowPlaying(GObject.Object, Peas.Activatable):
        __gtype_name__ = 'NowPlayingPlugin'
        object = GObject.property(type=GObject.Object)

        def do_activate(self):
                shell = self.object
                db = shell.get_property("db")

                # create Now Playing source
                self.__source = GObject.new(
                        NowPlayingSource,
                        shell=shell,
                        entry_type=RB.RhythmDB.get_song_entry_type(),
                        is_local=False,
                        plugin=self,
                        show_browser=False,
                        name=_("Now Playing")
                )

                # insert Now Playing source into Shared group
                shell.append_display_page(
                        self.__source,
                        RB.DisplayPageGroup.get_by_id("library"))
        
                self.__source.do_activate()                

        def do_deactivate(self):
                # destroy source
                self.__source.do_delete_thyself()
                del self.__source

