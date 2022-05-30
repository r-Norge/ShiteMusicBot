# Discord Packages
import discord

from .textpaginator import TextPaginator


class QueuePaginator(TextPaginator):
    def __init__(self, localizer, player, color, member: discord.Member = None, include_current: bool = False):
        self.localizer = localizer

        queue = player.global_queue() if not member else player.user_queue(member.id, dual=True)
        duration = player.queue_duration(member=member, include_current=include_current)

        if member:
            title = localizer.format_str("{queue.userqueue}",  _user=member.display_name, _length=len(queue),
                                         _duration=duration)
        else:
            title = localizer.format_str("{queue.length}", _length=len(queue), _duration=duration)

        super().__init__(max_lines=10, **{"color": color, "title": title})

        for index, temp in enumerate(queue):
            if member is None:
                track = temp
                queued_track = localizer.format_str("{queue.globaltrack}", _index=index+1,  _title=track.title,
                                                    _uri=track.uri, _user_id=track.requester)
            else:
                track, globpos = temp
                queued_track = localizer.format_str("{queue.usertrack}", _index=index+1, _globalindex=globpos+1,
                                                    _title=track.title, _uri=track.uri)

            self.add_line(queued_track)
        self.add_page_indicator(self.localizer, "{queue.pageindicator}")
