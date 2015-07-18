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
                if self.__activated:
                        print("SOURCE ALREADY ACTIVATED!")
                        return

                print("ACTIVATING SOURCE!")
                self.__activated = True

                # create menu to add items to Now Playng
                self.__action = Gio.SimpleAction(name="add-to-now-playing")
                self.__action.connect("activate", self.add_entries_callback)

                app = Gio.Application.get_default()
                app.add_action(self.__action)

                item = Gio.MenuItem()
                item.set_label("Add to Now Playing")
                item.set_detailed_action("app.add-to-now-playing")
                app.add_plugin_menu_item('browser-popup', 
                                        'add-to-now-playing', item)

                # Connect to row-inserted and row-deleted signals 
                # from "my own" QueryModel.
                # TODO: Why not use RBEntryView entry-added/deleted?
                signals = self.__signals = []
                query_model = self.props.base_query_model
                signals.append((query_model.connect("row-inserted",
                                        self.row_inserted_callback),
                                query_model))
                                
                signals.append((query_model.connect("row-deleted", 
                                        self.row_deleted_callback),
                                query_model))

                # Connect to ShellPlayer's "playing-source-changed"...
                shell_player = self.props.shell.props.shell_player
                signals.append((shell_player.connect(
                                        "playing-source-changed",
                                        self.source_changed_callback),
                                shell_player))
                # ... and "playing-changed".
                signals.append((shell_player.connect("playing-changed",
                                        self.playing_changed_callback),
                                shell_player))

                self.__playing_source = None
                self.create_sidebar()

        def do_can_rename(self):
                return False

        def do_delete_thyself(self):
                if not self.__activated:
                        print("SOURCE IS NOT ACTIVATED!")
                        return

                print("DEACTIVATING")
                # Remove menu action
                shell = self.props.shell
                app = Gio.Application.get_default()
                app.remove_action('add-to-now-playing')
                app.remove_plugin_menu_item('browser-popup', 'add-to-now-playing')
                del self.__action

                # Disconnect from signals
                for signal_id, signal_emitter in self.__signals:
                        signal_emitter.disconnect(signal_id)

                # Remove display page
                shell.props.display_page_model.remove_page(self)

                # Clear query model
                model = self.props.base_query_model
                iter = model.get_iter_first() 
                while(iter):    #FIXME: Isn't there an API call to clear the model!
                        entry_to_remove = model.iter_to_entry(iter)
                        if(entry_to_remove):
                                model.remove_entry(entry_to_remove)
                        iter = model.get_iter_first()

                self.__activated = False
                self.__playing_source = None
                self.get_property("shell").remove_widget (
                self.__sidebar, RB.ShellUILocation.RIGHT_SIDEBAR)
                # TODO: Delete the actual sidebar.

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

	        # Connect to the "entry-activated" signal of the sidebar
                sidebar.connect("entry-activated", self.sidebar_entry_activated)
                

        def sidebar_entry_activated(self, sidebar, selected_entry):
                player = self.get_property("shell").get_property("shell-player")
                player.play_entry(selected_entry, self)

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
                renderer.set_property(
                        "markup", markup)


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
        
        # When a source is selected to play, we intercept that call and replace
        # the selected source with the NowPlayingSource.
        # XXX: Replacing is not the most efficient/elegant solution...
        def source_changed_callback(self, player, new_source):
                if new_source == None:
                        print("NO SOURCE SELECTED")
                        return

                print("NEW SOURCE PLAYING: " + new_source.get_property("name"))

                if new_source == self:
                        print("IT'S US!!")
                        return

                # XXX: What if they are the same?
                if self.__playing_source == new_source:
                        print("SAME SOURCE, DOESNT COUNT")
                self.__playing_source = new_source
                self.__playing_source_view = new_source.get_entry_view()
                
                # FIXME: Should I be using base_query_model instead?
                query_model = self.props.query_model
                for treerow in query_model:     # Clear current selection
                        entry, path = list(treerow)
                        self.remove_entry(entry)
                for treerow in new_source.props.query_model: # Add new entries
                        entry, path = list(treerow)
                        self.add_entry(entry, -1)
                player.set_playing_source(self)
                self.__playing_source_view.set_state(RB.EntryViewState.PLAYING)


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

