from typing import Optional

import discord

from musicbot.utils.mixplayer.player import MixPlayer

from .textpaginator import TextPaginator


class QueuePaginator(TextPaginator):
    def __init__(self, localizer, player: MixPlayer, color: discord.Color,
                 member: Optional[discord.Member] = None, include_current: bool = False):
        self.localizer = localizer

        # Duration is calculated the same way for both global and user queues
        duration = player.queue_duration(member=member, include_current=include_current)

        if member:
            member_queue = player.user_queue_with_global_index(member)
            title = localizer.format_str("{queue.userqueue}",
                                         _user=member.display_name, _length=len(member_queue), _duration=duration)

            super().__init__(max_lines=10, **{"color": color, "title": title})

            # The user queues also inclue the global position of the tracks
            for index, (track, global_pos) in enumerate(member_queue):
                queued_track = localizer.format_str("{queue.usertrack}", _index=index+1, _globalindex=global_pos+1,
                                                    _title=track.title, _uri=track.uri)
                self.add_line(queued_track)
        else:
            queue = player.global_queue()
            title = localizer.format_str("{queue.length}", _length=len(queue), _duration=duration)

            super().__init__(max_lines=10, **{"color": color, "title": title})
            for index, track in enumerate(queue, start=1):
                queued_track = localizer.format_str("{queue.globaltrack}", _index=index,  _title=track.title,
                                                    _uri=track.uri, _user_id=track.requester)
                self.add_line(queued_track)
        self.add_page_indicator(self.localizer, "{queue.pageindicator}")
