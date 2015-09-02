# -*- Mode: python; coding: utf-8; tab-width: 8; indent-tabs-mode: t; -*-
# vim: expandtab shiftwidth=8 softtabstop=8 tabstop=8
#
# Copyright (C) 2015 - apnegrao
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.


import operator
import rb
from gi.repository import RB
from gi.repository import GObject
from gi.repository import Peas
from gi.repository import Gtk
from gi.repository import Gio

class NowPlayingSource(RB.StaticPlaylistSource):
        def __init__(self, **kwargs):
                super(NowPlayingSource,self).__init__(kwargs)
                self.__activated = False
                self.__playing_source = None
                self.__playing_source_signals = []
                self.__signals = None
                self.__filter = None
                self.__source_is_lib = False

        # Creates the actions and lib browser popup entries
        def setup_actions(self):
                app = Gio.Application.get_default()
                sidebar = self.__sidebar
                view = self.__entry_view
                player = self.get_property("shell").get_property("shell-player")
                browser_cb = self.add_entries_callback
                song_cb = self.menu_remove_song_callback
                rm_cb = self.menu_remove_by_prop_callback
                song = RB.RhythmDBPropType.TITLE
                album = RB.RhythmDBPropType.ALBUM
                artist = RB.RhythmDBPropType.ARTIST

                # Create action array:
                actions = [
                        # Add to Now Playing
                        ["add-song-to-np", browser_cb, song],
                        ["add-album-to-np", browser_cb, album],
                        ["add-artist-to-np", browser_cb, artist],
                        # Sidebar properties
                        ["sidebar-properties", self.sidebar_properties_callback],
                        # Clear
                        ["np-clear", self.clear_callback],
                        # Scroll to playing
                        ["np-scroll", self.scroll_callback, view],
                        ["np-bar-scroll", self.scroll_callback, sidebar],
                        # Remove song
                        ["np-bar-rm-song", song_cb, sidebar, True, player],
                        ["np-rm-song", song_cb, view, True, player],
                        ["np-bar-rm-other-song", song_cb, sidebar, False, player],
                        ["np-rm-other-song", song_cb, view, False, player],
                        # Remove
                        ["np-bar-rm-album", rm_cb, album, sidebar, True],
                        ["np-bar-rm-artist", rm_cb, artist, sidebar, True],
                        ["np-rm-album", rm_cb, album, view, True],
                        ["np-rm-artist", rm_cb, artist, view, True],
                        # Remove Other
                        ["np-bar-rm-other-album", rm_cb, album, sidebar, False],
                        ["np-bar-rm-other-artist", rm_cb, artist, sidebar, False],
                        ["np-rm-other-album", rm_cb, album, view, False],
                        ["np-rm-other-artist", rm_cb, artist, view, False]
                ]
                # Create, activate and add actions
                for entry in actions:
                        action = Gio.SimpleAction(name=entry[0])
                        action.connect("activate", *entry[1:])
                        app.add_action(action)

                # Create lib browser popup NP entries
                link = Gio.Menu()
                link.insert(-1, "Song", "app.add-song-to-np")
                link.insert(-1, "Album", "app.add-album-to-np")
                link.insert(-1, "Artist", "app.add-artist-to-np")
                menu = Gio.MenuItem()
                menu.set_label("Add to Now Playing")
                menu.set_submenu(link)
                app.add_plugin_menu_item('browser-popup', 'add-to-np-link', menu)

                # Create the context menus from XML
                builder = Gtk.Builder()
                filename = rb.find_plugin_file(self.plugin, "ui/rbnp_context_menu.ui")
                if not filename:
                        filename = "./ui/rbnp_context_menu.ui"
                builder.add_from_file(filename)
                self.__source_menu = builder.get_object("np-source-popup")
                self.__sidebar_menu = builder.get_object("np-sidebar-popup")


        # Activate source. Connects to signals, creates the menu actions
        # and draws the sidebar.
        def setup(self):
                if self.__activated:
                        return

                print("ACTIVATING SOURCE!")
                self.plugin = self.props.plugin
                self.__activated = True
                self.__entry_view = self.get_entry_view()
                self.__playing_source = None
                self.draw_sidebar()
                self.setup_actions()

                signals = self.__signals = []
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


        # Deactivates the source.
        def do_delete_thyself(self):
                if not self.__activated:
                        return

                print("DEACTIVATING")
                # Remove menu action
                app = Gio.Application.get_default()
                app.remove_action('add-to-now-playing')
                app.remove_plugin_menu_item('browser-popup', 'add-to-np')

                # Disconnect from signals
                for signal_id, signal_emitter in self.__signals:
                        signal_emitter.disconnect(signal_id)
                for signal_id, signal_emitter in self.__playing_source_signals:
                        signal_emitter.disconnect(signal_id)

                # Get the current playing status to use later
                shell = self.get_property("shell")
                player = shell.get_property("shell-player")
                ret, playing = player.get_playing()
                playing_entry = player.get_playing_entry()

                # Remove sidebar
                shell.remove_widget (self.__sidebar,
                        RB.ShellUILocation.RIGHT_SIDEBAR)
                # Remove display page
                shell.get_property("display-page-model").remove_page(self)
                # Stop playback. FIXME: Make this transition smoother.
                if playing:
                        player.stop()

        # Prevent the source page from being renamed.
        def do_can_rename(self):
                return False

        # For compatibility with RB version 3.1 (and lower?)
        def do_impl_can_rename(self):
                self.do_can_rename()

        # Updates the source page by showing only the entries that match the
        # search query inserted by the user. The search results do no influence
        # the play order, i.e., Now Playing will keep playing from the non filtered
        # query model.
        def do_search(self, search, cur_text, new_text):
                query_model = self.get_property("query-model")
                if len(new_text) > 0 and new_text != cur_text:
                        db = self.get_property("db")
                        search_results = search.create_query (db, new_text)
                        self.__filter = RB.RhythmDBQueryModel.new_empty (db)
                        self.__filter.set_property("base-model", query_model)

                        db.do_full_query_parsed(self.__filter, search_results)
                        self.__filter.reapply_query(True)
                        self.__entry_view.set_model(self.__filter)
                elif len(new_text) == 0:
                        self.__filter = None
                        self.__entry_view.set_model(query_model)

        # For compatibility with RB version 3.1 (and lower?)
        def do_impl_search(self, search, cur_text, new_text):
                self.do_search(search, cur_text, new_text)

        # Shows the context menu of either the sidebar or the source page.
        def do_show_entry_view_popup(self, view, over_entry):
                if view == self.__sidebar:
                        menu = Gtk.Menu.new_from_model(self.__sidebar_menu)
                else:
                        menu = Gtk.Menu.new_from_model(self.__source_menu)
                menu.attach_to_widget(self, None)
                menu.popup(None, None, None, None, 3, Gtk.get_current_event_time())

        # For compatibility with RB version 3.1 (and lower?)
        def do_impl_show_entry_view_popup(self, view, over_entry):
                self.do_show_entry_view_popup(view, over_entry)

       # Draws the Now Playing sidebar.
        def draw_sidebar(self):
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
                shell.add_widget (sidebar, RB.ShellUILocation.RIGHT_SIDEBAR,
                        True, True)
                sidebar.set_visible(True)
                sidebar.show_all()

	        # Connect to the "entry-activated" signal of the sidebar
                sidebar.connect("entry-activated",
                        self.sidebar_entry_activated_callback)

        # Cell data func used by the sidebar to format the output of the entries.
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

        # Updates the titles of the sidebar and the source page to show the
        # number of songs in the Now Playing playlist (if any).
        def update_titles(self):
                model = self.__sidebar.get_property("model")
                name = base_name = _("Now Playing")
                count = model.iter_n_children(None)
                if count > 0:
                        name = base_name + " (" + str(count) + ")"
                self.set_property("name", name)
                self.__sidebar_column.set_title(name)


        # Returns the values of property 'prop' for each entry selected
        # in 'view'.
        def gather_selected_properties_for_view(self, view, prop):
                if view == self.__entry_view:
                        return set(self.gather_selected_properties (prop))
                else:
                        selected_entries = view.get_selected_entries()
                        prop_keys = set()
                        for entry in selected_entries:
                                prop_keys.add(entry.get_string(prop))
                        return prop_keys

        # Returns all the entries in 'model' whose 'prop' value matches one
        # of the values in 'sel_props' ('sel_matching' = True) or all the entries
        # in 'model' whose 'prop' values doesn't match any value in 'sel_props'
        # ('sel_matching' = False)
        def gather_entries_by_prop(self, model, sel_props, prop, sel_matching):
                entries = []
                model.foreach(self.select_entry_by_prop, prop,
                        sel_props, entries, sel_matching)
                return entries

        # Used by 'gather_entries_by_prop' (called by the foreach
        # function of the query model). Iteratively contructs a list with the
        # entries that match/don't match a given property. If 'select_matching'
        # is True, the entry (given by 'iter') is selected if the value of its
        # 'prop' property is in 'prop_set'. If 'select_matching' is False, the
        # entry is selected is 'prop' is not in 'prop_set'.
        def select_entry_by_prop(self, model, path, iter, prop, prop_set,
                        selected_entries, select_matching):
                def xor(A, B):
                        return A != B
                entry = model.iter_to_entry(iter)
                entry_prop = entry.get_string(prop)
                if not xor(entry_prop in prop_set, select_matching):
                        selected_entries.append(entry)
                return False

        # Clears the Now Playing playlist database and updates the
        # entry views.
        def clear(self):
                db = self.get_property("db")
                new_model = RB.RhythmDBQueryModel.new_empty(
                        self.get_property("db"))
                self.set_query_model(new_model)
                self.__sidebar.set_model(new_model)
                self.update_titles()

        #####################################################################
        #                       CALLBACKS                                   #
        #####################################################################
        #############################SIGNALS#################################
        # When a source is selected to play, we intercept that call and replace
        # the selected source with the NowPlayingSource.
        # XXX: Replacing is not the most efficient/elegant solution...
        def source_changed_callback(self, player, new_source):
                if new_source == None:
                        print("NO SOURCE SELECTED")
                        return

                print("NEW SOURCE PLAYING: " + new_source.get_property("name"))

                if new_source == self:  # XXX: This should no longer be possible
                        print("IT'S US!!")
                        return

                # This seems to occur only when returning from Stop. Let's just
                # resume playing from the Now Playing playlist. XXX: If the user
                # wants to select something else, he needs to double click on it.
                model = self.get_property("query_model")
                empty_model = model.get_iter_first() is None
                source_is_new = self.__playing_source != new_source
                if not source_is_new and not empty_model:
                        print("SAME SOURCE, IGNORING SELECTION")
                        # FIXME: I'm complicating things: just start
                        # playing from the top of the playlist.
                        ret, playing = player.get_playing()
                        if not playing:
                                return
                        bar_entries = self.__sidebar.get_selected_entries()
                        page_entries = self.__entry_view.get_selected_entries()
                        entry_to_play = None
                        if bar_entries:
                                entry_to_play = bar_entries[0]
                        elif page_entries:
                                entry_to_play = page_entries[0]
                        else:
                                iter = model.get_iter_first()
                                entry_to_play = model.iter_to_entry(iter)
                        player.play_entry(entry_to_play, self.__playing_source)
                        return

                if empty_model and not source_is_new:# Restore playing source data
                        self.__playing_source.set_property("query-model",
                                self.__playing_source_model)

                # If new source is different
                if source_is_new:
                        # Disconnect from signals
                        for signal_id, emiter in self.__playing_source_signals:
                                emiter.disconnect(signal_id)
                        self.__playing_source_signals = []
                        # Set new data
                        self.__playing_source = new_source
                        self.__playing_source_model = \
                                new_source.get_property("query-model")

                if new_source.get_entry_view() and self.__playing_source_model:
                        # Clear current selection
                        self.clear()
                        # Add new entries
                        query_model = self.get_property("query-model")
                        query_model.copy_contents(self.__playing_source_model)
                        shell = self.get_property("shell")
                        lib_source = shell.get_property("library-source")
                        if new_source == lib_source:
                                new_source.set_property("query-model", query_model)
                                self.__source_is_lib = True
                        else:
                                self.__source_is_lib = False
                        if source_is_new: # Connect only if new source is new
                                self.connect_signals_for_control(new_source)
                self.update_titles()

        def connect_signals_for_control(self, new_source):
                signals = self.__playing_source_signals = []
                playing_source_view = new_source.get_entry_view()
                id = new_source.connect("filter-changed",
                        self.filter_changed_callback)
                signals.append((id, new_source))
                id = playing_source_view.connect("entry-activated",
                        self.entry_activated)
                signals.append((id, playing_source_view))
                for prop_view in new_source.get_property_views():
                      id = prop_view.connect("property_activated",
                            self.property_activated)
                      signals.append((id, prop_view))
                if not self.__source_is_lib:
                        # FIXME: For Playlist sources use the "base-query-model"
                        new_source_model = new_source.get_property("query-model")
                        id = new_source_model.connect("row_inserted",
                                self.row_inserted_callback)
                        signals.append((id, new_source_model))
                        id = new_source_model.connect("row-deleted",
                                self.row_deleted_callback)
                        signals.append((id, new_source_model))

        def row_inserted_callback(self, model, path, iter):
                query_model = self.get_property("query-model")
                print("ROW INSERTED")
                entry = model.iter_to_entry(iter)
                index = path.get_indices()[0]
                query_model.add_entry(entry, index)
                #self.update_titles()

        def row_deleted_callback(self, model, path):
                query_model = self.get_property("query-model")
                if query_model.iter_n_children() == 0:
                        # XXX: This only happens after a clear, which leaves the
                        # NP query_model empty, but doesn't clear the query_model
                        # of the __playing_source.
                        return
                print("ROW DELETED")
                entry = query_model.tree_path_to_entry(path)
                query_model.remove_entry(entry)
                #self.update_titles()

        def filter_changed_callback(self, source):
                print("FILTER CHANGED!")
                if self.__playing_source == None:
                        return
                self.__playing_source_model = source.get_property("query-model")
                model = self.get_property("query-model")
                source.set_property("query-model", model)

        def property_activated(self, prop_view, prop_name):
                print("PROPERTY ACTIVATED")
                source = self.__playing_source
                new_model = source.get_entry_view().get_property("model")
                iter = new_model.get_iter_first()
                if not iter:   # The query-model of the source has not yet been
                        return  # updated.
                # Clear current selection
                self.clear()
                # Add new entries
                query_model = self.get_property("query-model")
                query_model.copy_contents(new_model)
                player = self.get_property("shell").get_property("shell-player")
                entry = query_model.iter_to_entry(query_model.get_iter_first())
                player.play_entry(entry, source)
                source.set_property("query-model", query_model)
                self.update_titles()

        def entry_activated(self, view, entry):
                print("ENTRY ACTIVATED")
                 # Clear current selection
                self.clear()
                # Add new entries
                source = self.__playing_source
                new_model = source.get_entry_view().get_property("model")
                query_model = self.get_property("query-model")
                query_model.copy_contents(new_model)
                source.set_property("query-model", query_model)
                self.update_titles()

        # Callback to the "entry-activated" signal of the sidebar. Selects the
        # activated entry as the playing entry.
        def sidebar_entry_activated_callback(self, sidebar, selected_entry):
                player = self.get_property("shell").get_property("shell-player")
                player.play_entry(selected_entry, self.__playing_source)


        # Updates the playing status symbol (play/pause) next to the playing
        # entry in the NowPlaying source page and sidebar.
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

                # Scroll to playing entry.
                # FIXME: Scroll only if it isn't visible.
                # FIXME: Stop auto scrolling after adding 'Scroll to playing'
                playing_entry = player.get_playing_entry()
                if playing_entry:
                        entry_view.scroll_to_entry(playing_entry)
                        sidebar.scroll_to_entry(playing_entry)

        #################################ACTIONS#############################

        # Callback to the clear action of the context menus.
        def clear_callback(self, action, data):
                self.clear()
                player = self.get_property("shell").get_property("shell-player")
                player.stop()

        # Callback for the 'Remove'/'Remove other' context menu actions.
        # Removes the selected song if 'remove_selected' is True; removes all
        # other songs if 'remove_selected' is false.
        def menu_remove_song_callback(self, action, data, view, remove_selected,
                        player):
                selected_entries = view.get_selected_entries()
                if remove_selected:
                        model = self.get_property("query-model")
                        if not self.__source_is_lib:
                                model = self.__playing_source_model
                        for entry in selected_entries:
                                model.remove_entry(entry)
                else:
                        # If the playing source is the lib, we can optimize
                        # the remove process by clearing the current selection
                        # instead of removing entry by entry.
                        if self.__source_is_lib:
                                self.clear()
                                model = self.get_property("query-model")
                                self.__playing_source.set_property("query-model", model)
                                for entry in selected_entries:
                                        model.add_entry(entry, -1)
                                playing_entry = player.get_playing_entry()
                                if not playing_entry in selected_entries:
                                        player.do_next()
                        # If the playing source is a non native source, we cannot
                        # do the same optimization because we don't know its
                        # internals.
                        else:
                                model = self.get_property("query-model")
                                if not self.__source_is_lib:
                                        model = self.__playing_source_model
                                for treerow in model:
                                        entry, path = list(treerow)
                                        if not entry in selected_entries:
                                                model.remove_entry(entry)
                self.update_titles()


        # Callback for the 'Remove' and 'Remove Other' actions of the context
        # menus of both the sidebar and the source page. Removes from 'view' all
        # the entries that have ('Remove') or do not have ('Remove Other') the
        # same values for property 'prop' as the selected entries, depending on
        # the value of 'remove_matching' (True = 'Remove', False = 'Remove Other').
        # TODO: Maybe I can optimize the 'Remove Other' process by first clearing
        # the current model and then adding the entries to keep. Not doing it right
        # now because foreach does not iterate in song order.
        def menu_remove_by_prop_callback(self, action, data, prop, view,
                        remove_matching):
                model = self.get_property("query-model")
                selected_props = self.gather_selected_properties_for_view(
                        view, prop)
                entries_to_remove = self.gather_entries_by_prop(
                                model, selected_props, prop, remove_matching)
                for entry in entries_to_remove:
                        if not self.__source_is_lib:
                                model = self.__playing_source_model
                        model.remove_entry(entry)
                self.update_titles()

        # Callback for the 'Add to Now Playing' action we added to the context
        # menu of the library. The 'add_key' param is an RB.RhythmDBPropType that
        # determines what should be added (song, album or artist)
        def add_entries_callback(self, action, data, add_key):
                model = self.get_property("query-model")
                shell = self.get_property("shell")
                lib_source = shell.get_property("library-source")
                lib_view = lib_source.get_entry_view()
                entries_to_add = []
                if add_key == RB.RhythmDBPropType.TITLE:
                        entries_to_add = lib_view.get_selected_entries()
                else:
                        sel_props = lib_source.gather_selected_properties(add_key)
                        lib_model = lib_source.get_property("base_query_model")
                        entries_to_add = self.gather_entries_by_prop(
                                lib_model, sel_props, add_key, True)
                for entry in entries_to_add:
                        model.add_entry(entry, -1)
                self.update_titles()
                return

        # Callback for the 'Properties' action of the sidebar's context menu.
        def sidebar_properties_callback(self, action, data):
                song_info = RB.SongInfo.new(self, self.__sidebar)
                song_info.show_all()

        # Callback for the 'Scroll to Playing' action.
        def scroll_callback(self, action, data, view):
                player = self.get_property("shell").get_property("shell-player")
                playing_entry = player.get_playing_entry()
                if playing_entry:
                        view.scroll_to_entry(playing_entry)

###################################################
#                 PLUGIN INIT CODE                #
###################################################
class NowPlaying(GObject.Object, Peas.Activatable):
        __gtype_name__ = 'NowPlayingPlugin'
        object = GObject.property(type=GObject.Object)

        def __init__(self):
		        GObject.Object.__init__(self)

        def do_activate(self):
                shell = self.object

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

                self.__source.setup()

                # insert Now Playing source into Shared group
                shell.append_display_page(
                        self.__source,
                        RB.DisplayPageGroup.get_by_id("library"))

        def do_deactivate(self):
                # destroy source
                self.__source.do_delete_thyself()
                del self.__source

GObject.type_register(NowPlayingSource)
