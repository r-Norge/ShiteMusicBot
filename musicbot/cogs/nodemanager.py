import codecs
from typing import List, Optional, Union

import discord
import lavalink
from discord.ext import commands

import yaml

from bot import MusicBot
from musicbot.cogs.music.music_errors import MusicError
from musicbot.utils.mixplayer import MixPlayer
from musicbot.utils.settingsmanager import Settings
from musicbot.utils.userinteraction import ClearMode, Scroller

from .helpformatter import commandhelper


class NodeManager(commands.Cog):
    def __init__(self, bot: MusicBot):
        self.bot: MusicBot = bot
        self.settings: Settings = self.bot.settings
        self.logger = self.bot.main_logger.bot_logger.getChild("NodeManager")

    async def load_music_cogs(self):
        music_extensions = [
            'musicbot.cogs.music',
        ]

        if self.bot.lavalink is None and self.bot.user:
            self.bot.lavalink = lavalink.Client(self.bot.user.id, player=MixPlayer)
            self.lavalink = self.bot.lavalink

            self.load_nodes_from_file()

            self.bot.add_listener(self.bot.lavalink.voice_update_handler, 'on_socket_response')

            for extension in music_extensions:
                try:
                    self.logger.debug("Loading extension %s" % extension)
                    await self.bot.load_extension(extension)
                except Exception:
                    self.logger.exception("Loading of extension %s failed" % extension)
        else:
            self.logger.error("Failed to initialize lavalink client")
            raise MusicError("Failed to initialize lavalink client")

    def load_nodes_from_file(self):
        with codecs.open(f"{self.bot.datadir}/config.yaml", 'r', encoding='utf8') as f:
            conf = yaml.load(f, Loader=yaml.SafeLoader)

            name_cache = []
            new_nodes = []

            for node in self.lavalink.node_manager.nodes:
                name_cache.append(node.name)

            for node in conf['lavalink nodes'] + self.settings.get('lavalink', 'nodes', []):
                if node['name'] in name_cache:
                    continue

                added = self.lavalink.add_node(**node)

                self.logger.debug("Adding Lavalink node: %s on %s with the port %s in %s" % (
                    node['name'], node['host'],
                    node['port'], node['region'],))
                new_nodes.append(added)
                name_cache.append(node['name'])
            return new_nodes

    async def _regioner(self, region):
        flags = {
            'us': ':flag_us:',
            'eu': ':flag_eu:',
            'singapore': ':flag_sg:',
            'london': ':flag_gb:',
            'sydney': ':flag_au:',
            'amsterdam': ':flag_nl:',
            'frankfurt': ':flag_de:',
            'brazil': ':flag_br:',
            'japan': ':flag_jp:',
            'russia': ':flag_ru:',
            'southafrica': ':flag_za:',
            'hongkong': ':flag_hk:',
            'india': ':flag_in:'
        }
        try:
            return flags[region]
        except KeyError:
            return ':question:'

    async def _node_presenter(self, ctx, node: Union[List[lavalink.Node], lavalink.Node]):
        embed = discord.Embed(color=ctx.me.color)
        embed.title = 'Added new node!'

        if isinstance(node, list):
            for n in node:
                embed.add_field(name=f'{await self._regioner(n.region)} **Name:** {n.name}',
                                value=f'**Host:** {n._transport._host}\n **Port:** {n._transport._port}')

        if isinstance(node, lavalink.Node):
            embed.add_field(name=f'{await self._regioner(node.region)} **Name:** {node.name}',
                            value=f'**Host:** {node._transport._host}\n **Port:** {node._transport._port}')

        return embed

    def get_node_properties(self, node: lavalink.Node):
        return {
            'name': node.name,
            'host': node._transport._host,
            'port': node._transport._port,
            'password': node._transport._password,
            'region': node.region
        }

    @commands.group(name='node', hidden=True)
    @commands.is_owner()
    async def _node(self, ctx):
        if ctx.invoked_subcommand is None:
            ctx.localizer.prefix = 'help'  # Ensure the bot looks for locales in the context of help, not cogmanager.
            paginator = commandhelper(ctx, ctx.command, ctx.invoker, include_subcmd=True)
            scroller = Scroller(ctx, paginator)
            await scroller.start_scrolling(ClearMode.AnyExit)

    @_node.command(name='reload_file')
    @commands.is_owner()
    async def reload_file(self, ctx):
        for node in self.load_nodes_from_file():
            embed = await self._node_presenter(ctx, node)
            embed.title = 'Added new node from file!'
            await ctx.send(embed=embed)

    @_node.command(name='add')
    @commands.is_owner()
    async def _add(self, ctx, host: str, port: int, password: str, region, name: Optional[str] = None):
        if name in [n.name for n in self.lavalink.node_manager.nodes]:
            return await ctx.send("A node with that name already exists")

        node = self.lavalink.add_node(host, port, password, region, name=name)
        self.logger.debug("Adding Lavalink node: %s", (node))

        embed = await self._node_presenter(ctx, node)
        embed.title = 'Added new node!'

        self.settings.set('lavalink', 'nodes', [self.get_node_properties(n) for
                                                n in self.lavalink.node_manager.nodes])
        await ctx.send(embed=embed)

    @_node.command(name='list')
    @commands.is_owner()
    async def list_nodes(self, ctx):
        embed = await self._node_presenter(ctx, self.lavalink.node_manager.nodes)
        embed.title = 'Lavalink nodes attatched to this bot:'
        await ctx.send(embed=embed)

    @_node.command(name='remove')
    @commands.is_owner()
    async def _remove(self, ctx, node):
        sent_feedback = False
        for _node in self.lavalink.node_manager.nodes:
            if len(self.lavalink.node_manager.nodes) <= 1:
                await ctx.send('Cannot remove the last node')
                sent_feedback = True
                break
            if _node.name == node:
                sent_feedback = True
                embed = await self._node_presenter(ctx, _node)
                embed.title = 'Removed node from bot'
                await ctx.send(embed=embed)
                self.lavalink.node_manager.remove(_node)
                await _node.destroy()
                self.logger.info("Removed Lavalink node: %s" % (_node.name))

        self.settings.set('lavalink', 'nodes', [self.get_node_properties(n) for
                                                n in self.lavalink.node_manager.nodes])

        if not sent_feedback:
            await ctx.send('No node found')

    @_node.command(name='change')
    @commands.is_owner()
    async def _nodechange(self, ctx, node=None):
        player = self.lavalink.player_manager.get(ctx.guild.id)

        if not player:
            return

        # "Switches" to the current node
        if node is None:
            await player.change_node(player.node)

        else:
            newnode = None
            for _node in self.lavalink.node_manager.nodes:
                if _node.name == node:
                    newnode = _node

            if not newnode:
                return
            await player.change_node(newnode)


async def setup(bot):
    cog = NodeManager(bot)
    await cog.load_music_cogs()
    await bot.add_cog(cog)
