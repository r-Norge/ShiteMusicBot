# Discord Packages
import discord
from discord.ext import commands
from lavalink import Client, Node

import codecs

import yaml

# Bot Utilities
from musicbot.utils.settingsmanager import Settings
from ..utils.mixplayer import MixPlayer
from ..utils.userinteraction import ClearOn, Scroller
from .helpformatter import commandhelper


class NodeManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings: Settings = self.bot.settings
        self.logger = self.bot.main_logger.bot_logger.getChild("NodeManager")

    async def load_music_cogs(self):
        music_extensions = [
            'musicbot.cogs.music',
        ]

        if not hasattr(self.bot, 'lavalink'):
            self.bot.lavalink = Client(self.bot.user.id, player=MixPlayer)

            self.load_nodes_from_file()

            self.bot.add_listener(self.bot.lavalink.voice_update_handler, 'on_socket_response')

            for extension in music_extensions:
                try:
                    self.logger.debug("Loading extension %s" % extension)
                    await self.bot.load_extension(extension)
                except Exception:
                    self.logger.exception("Loading of extension %s failed" % extension)

    def load_nodes_from_file(self):
        with codecs.open(f"{self.bot.datadir}/config.yaml", 'r', encoding='utf8') as f:
            conf = yaml.load(f, Loader=yaml.SafeLoader)

            name_cache = []
            new_nodes = []

            for node in self.bot.lavalink.node_manager.nodes:
                name_cache.append(node.name)

            self.logger.debug("BEFORE")
            for node in conf['lavalink nodes'] + self.settings.get('lavalink', 'nodes', []):
                if node['name'] in name_cache:
                    continue

                self.bot.lavalink.add_node(**node)

                self.logger.debug("Adding Lavalink node: %s on %s with the port %s in %s" % (
                    node['name'], node['host'],
                    node['port'], node['region'],))
                new_nodes.append({**node})
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

    async def _node_presenter(self, ctx, node):
        embed = discord.Embed(color=ctx.me.color)
        embed.title = 'Added new node!'

        if isinstance(node, list):
            for n in node:
                embed.add_field(name=f'{await self._regioner(n.region)} **Name:** {n.name}',
                                value=f'**Host:** {n.host}\n **Port:** {n.port}')

        if isinstance(node, Node):
            embed.add_field(name=f'{await self._regioner(node.region)} **Name:** {node.name}',
                            value=f'**Host:** {node.host}\n **Port:** {node.port}')

        if isinstance(node, dict):
            embed.description = f'**Name:** {node.get("name")}\n **Host:** {node.get("host")}\n ' \
                f'**Port:** {node.get("port")}\n **Region:** {await self._regioner(node.get("region"))}'

        return embed

    def get_node_properties(self, node):
        return {
            'name': node.name,
            'host': node.host,
            'port': node.port,
            'password': node.password,
            'region': node.region
        }

    @commands.group(name='node', hidden=True)
    @commands.is_owner()
    async def _node(self, ctx):
        if ctx.invoked_subcommand is None:
            ctx.localizer.prefix = 'help'  # Ensure the bot looks for locales in the context of help, not cogmanager.
            paginator = commandhelper(ctx, ctx.command, ctx.invoker, include_subcmd=True)
            scroller = Scroller(ctx, paginator)
            await scroller.start_scrolling(ClearOn.AnyExit)

    @_node.command(name='reload_file')
    @commands.is_owner()
    async def reload_file(self, ctx):
        for node in self.load_nodes_from_file():
            embed = await self._node_presenter(ctx, node)
            embed.title = 'Added new node from file!'
            await ctx.send(embed=embed)

    @_node.command(name='add')
    @commands.is_owner()
    async def _add(self, ctx, host, port, password, region, name=None):
        if name in [n.name for n in self.bot.lavalink.node_manager.nodes]:
            return await ctx.send("A node with that name already exists")

        self.bot.lavalink.add_node(host, port, password, region, name=name)
        self.logger.debug("Adding Lavalink node: %s on %s with the port %s in %s" % (host, port, region, name,))
        embed = await self._node_presenter(ctx, {'host': host, 'port': port, 'password': password,
                                                 'region': region, 'name': name})
        embed.title = 'Added new node!'

        self.settings.set('lavalink', 'nodes', [self.get_node_properties(n) for
                                                n in self.bot.lavalink.node_manager.nodes])
        await ctx.send(embed=embed)

    @_node.command(name='list')
    @commands.is_owner()
    async def list_nodes(self, ctx):
        embed = await self._node_presenter(ctx, self.bot.lavalink.node_manager.nodes)
        embed.title = 'Lavalink nodes attatched to this bot:'
        await ctx.send(embed=embed)

    @_node.command(name='remove')
    @commands.is_owner()
    async def _remove(self, ctx, node):
        sent_feedback = False
        for _node in self.bot.lavalink.node_manager.nodes:
            if len(self.bot.lavalink.node_manager.nodes) <= 1:
                await ctx.send('Cannot remove the last node')
                sent_feedback = True
                break
            if (_node.name or _node.host) == node:
                sent_feedback = True
                embed = await self._node_presenter(ctx, _node)
                embed.title = 'Removed node from bot'
                await ctx.send(embed=embed)
                self.bot.lavalink.node_manager.remove_node(_node)
                self.logger.info("Removed Lavalink node: %s, %s" % (_node.name, _node.host))

        self.settings.set('lavalink', 'nodes', [self.get_node_properties(n) for
                                                n in self.bot.lavalink.node_manager.nodes])

        if not sent_feedback:
            await ctx.send('No node found')

    @_node.command(name='change')
    @commands.is_owner()
    async def _nodechange(self, ctx, node=None):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player:
            return

        # "Switches" to the current node
        if node is None:
            await player.change_node(player.node)

        else:
            newnode = None
            for _node in self.bot.lavalink.node_manager.nodes:
                if (_node.name or _node.host) == node:
                    newnode = _node

            if not newnode:
                return
            await player.change_node(newnode)


async def setup(bot):
    cog = NodeManager(bot)
    await cog.load_music_cogs()
    await bot.add_cog(cog)
