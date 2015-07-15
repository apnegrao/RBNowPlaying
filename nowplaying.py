# -*- Mode: python; coding: utf-8; tab-width: 8; indent-tabs-mode: t; -*-
# vim: expandtab shiftwidth=8 softtabstop=8 tabstop=8

import os

import rb, operator
from gi.repository import RB
from gi.repository import GObject, Peas, Gtk, Gio, GdkPixbuf

class NowPlayingSource(RB.StaticPlaylistSource):
        def __init__(self):
                super(NowPlayingSource,self).__init__()
                self.__activated = False

        def do_activate(self):
                print("ACTIVATING SOURCE!")
                if not self.__activated:
                        self.__activated = True

                        # create menu to add items to Now Playng
                        self.__action = Gio.SimpleAction(name="add-to-now-playing")
                        self.__action.connect("activate", self.add_entries_callback)

                        app = Gio.Application.get_default()
                        app.add_action(self.__action)

                        item = Gio.MenuItem()
                        item.set_label("Add to Now Playing")
                        item.set_detailed_action("app.add-to-now-playing")
                        app.add_plugin_menu_item('browser-popup', 'add-to-now-playing', item)

                        # Connect to row-inserted and row-deleted signals from "my own" QueryModel
                        # (inherited from GTKTreeModel.
                        # TODO: Why not listen to entry-added/deleted from RBEntryView?
                        self.props.base_query_model.connect(
                                "row-inserted",
                                self.row_inserted_callback)
                        self.props.base_query_model.connect(
                                "row-deleted", 
                                self.row_deleted_callback)

                        # Connect to ShellPlayer's "playing-source-changed"...
                        shell_player = self.props.shell.props.shell_player
                        self.__source_changed_signal_id = shell_player.connect(
                                "playing-source-changed",
                                self.source_changed_callback)

                        # and "playing-changed"...
                        self.__source_changed_signal_id = shell_player.connect(
                                "playing-changed",
                                self.playing_changed_callback)

                        # and "playing-song-changed"...
                        self.__source_changed_signal_id = shell_player.connect(
                                "playing-song-changed",
                                self.playing_song_changed_callback)

                        self.__playing_source = None
                        self.create_sidebar()

        def do_can_rename(self):
                return False

        def do_delete_thyself(self):
                print("Deactivating")
                if self.__activated:
                        # Remove menu action
                        shell = self.props.shell
                        app = Gio.Application.get_default()
                        app.remove_action('add-to-now-playing')
                        app.remove_plugin_menu_item('browser-popup', 'add-to-now-playing')
                        del self.__action

                        # Remove display page
                        shell.props.display_page_model.remove_page(self)

                        # Clear query model
                        model = self.props.base_query_model
                        iter = model.get_iter_first() 
                        while(iter):
                                entry_to_remove = model.iter_to_entry(iter)
                                if(entry_to_remove):
                                        model.remove_entry(entry_to_remove)
                                iter = model.get_iter_first()

                        self.__activated = False

        def create_sidebar(self):
                shell = self.props.shell
                sidebar = self.__sidebar = RB.EntryView.new(
                        shell.props.db, 
                        shell.props.shell_player, 
                        True, True)

                sidebar.set_property("vscrollbar-policy", Gtk.PolicyType.AUTOMATIC)
                sidebar.set_property("shadow-type", Gtk.ShadowType.NONE)
                sidebar.get_style_context().add_class("nowplaying-sidebar")

                renderer = Gtk.CellRendererText.new()
                sidebar_column = Gtk.TreeViewColumn.new()
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

	        #/* sync the state of the main entry view and the sidebar */
	        #g_signal_connect_object (G_OBJECT (rb_source_get_entry_view (RB_SOURCE (source))),
	        #			 "notify::playing-state",
	        #			 G_CALLBACK (rb_play_queue_sync_playing_state),
	        #			 source, 0);

        def cell_data_func(self, sidebar_column, renderer, tree_model, iter, data):
                db = self.get_property("shell").get_property("db")
                entry = tree_model.get(iter, 0)[0]
                title = entry.get_string(RB.RhythmDBPropType.TITLE)
                #db.entry_get(entry, RB.RhythmDBPropType.TITLE, title)
                artist = entry.get_string(RB.RhythmDBPropType.ARTIST)
                #db.entry_get(entry, RB.RhythmDBPropType.ARTIST, artist)
                album = entry.get_string(RB.RhythmDBPropType.ALBUM)
                #db.entry_get(entry, RB.RhythmDBPropType.ALBUM, album)
        	# Translators: format is "<title> from <album> by <artist>"
                markup = GObject.markup_escape_text(title) + \
                        "\n<span size=\"smaller\">from <i>" + \
                        GObject.markup_escape_text(album) \
                        + "</i>\nby <i>" + GObject.markup_escape_text(artist) \
                        + "</i></span>"
                renderer.set_property(
                        "markup", markup)
	        #g_object_set (G_OBJECT (renderer), "markup", markup, NULL);


        #####################################################################
        #                       CALLBACKS                                   #
        #####################################################################

        # Callback to the "row_inserted" signal to RBEntryView.
        # Updates the song number shown in brackets in the display tree.
        def row_inserted_callback(self, model, tree_path, iter):
                base_name = _("Now Playing")
                count = model.iter_n_children(None)
                if count > 0:
                        self.props.name = base_name + " (" + str(count) + ")"
                else:
                        self.props.name = base_name

        # Callback to the "row_inserted" signal to RBEntryView.
        # Updates the song number shown in brackets in the display tree.
        def row_deleted_callback(self, model, tree_path):
                count = model.iter_n_children(None)
                base_name = _("Now Playing")
                if count -1 > 0:
                        self.props.name = base_name + " (" + str(count - 1) + ")"
                else:
                        self.props.name = base_name

        
        # Updates the playing status symbol (play/pause) next to the playing
        # entry in the NowPlaying source. 
        def playing_changed_callback(self, player, playing):
                print("PLAY STATE CHANGED!")
                entry_view = super(RB.StaticPlaylistSource, self).get_entry_view()
                sidebar = self.__sidebar
                state = None
                if playing:
                        state = RB.EntryViewState.PLAYING
                else:
                        state = RB.EntryViewState.PAUSED
                entry_view.set_state(state)
                sidebar.set_state(state)
        
        # XXX: This looks overly simplistic, but lets keep it this way for now.
        def source_changed_callback(self, player, new_source):
                if new_source == None:
                        print("NO SOURCE SELECTED")
                        return

                if new_source == self:
                        print("IT'S US!!")
                        return

                print("NEW SOURCE PLAYING")
                if self.__playing_source: # A source was already selected.
                        # 1st, disconnect from previous source's entry view...
                        self.__playing_source_view.disconnect(
                                 self.__playing_source_view_signal_id)
                        # ...and property view(s)
                        for prop_view, signal_id in self.__prop_views:
                                prop_view.disconnect(signal_id)
                
                # What if they are the same?
                if self.__playing_source == new_source:
                        print("SAME SOURCE, DOESNT COUNT")
                self.__playing_source = new_source
                self.__playing_source_view = new_source.get_entry_view()
                # Connect to "entry-activated" for "click to play" actions
                self.__playing_source_view_signal_id = self.__playing_source_view.connect(
                                "entry-activated",
                                self.playing_entry_changed_callback)
                # FIXME: Should I be using base_query_model instead?
                query_model = self.props.query_model
                for treerow in query_model:     # Clear current selection
                        entry, path = list(treerow)
                        self.remove_entry(entry)
                for treerow in new_source.props.query_model:    # Add new entries
                        entry, path = list(treerow)
                        self.add_entry(entry, -1)

                playing_entry = player.get_playing_entry()
                res, playing_state = player.get_playing()

                # Source is RB's LibrarySource
                shell = self.props.shell
                self.__prop_views = []
                if new_source == shell.props.library_source:
                        print("IT'S THE LIB SOURCE!")
                        # Connect to "property-activate"
                        prop_views = new_source.get_property_views()
                        for prop_view in prop_views:
                                signal_id = prop_view.connect(
                                        "property_activated", 
                                        self.property_activated_callback)
                        #shell.activate_source(self, 1)
                        player.set_playing_source(self)
                        lib_entry_view = new_source.get_entry_view()
                        lib_entry_view.set_state(RB.EntryViewState.PLAYING)

                # Source is a Playlist (Static or Queue).
                # FIXME: What about Auto?

        def property_activated_callback(self, prop_view, name):
                print("PROPERTY VIEW SELECTED {}".format(name))
                # FIXME: Should I be using base_query_model instead?
                query_model = self.props.query_model
                for treerow in query_model:     # Clear current selection
                        entry, path = list(treerow)
                        self.remove_entry(entry)
                selection = self.__playing_source.props.query_model
                for treerow in selection:    # Add new entries
                        #print(treerow)
                        entry, path = list(treerow)
                        self.add_entry(entry, -1)
                #playing_entry = player.get_playing_entry()
                #res, playing_state = player.get_playing()

        def playing_entry_changed_callback(self, view, playing_entry):
                print("NEW PLAYING ENTRY")

        def playing_song_changed_callback(self, player, playing):
                print("PLAYING SONG CHANGED!")
               
        def add_entries_callback(self, action, data):
                library_source = self.props.shell.props.library_source
                selected = library_source.get_entry_view().get_selected_entries()
                for selected_entry in selected:
                        self.add_entry(selected_entry, -1)
                return


class NowPlaying(GObject.Object, Peas.Activatable):
        __gtype_name__ = 'NowPlayingPlugin'
        object = GObject.property(type=GObject.Object)

        def do_activate(self):
                shell = self.object
                db = shell.props.db

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
                self.__source = None

