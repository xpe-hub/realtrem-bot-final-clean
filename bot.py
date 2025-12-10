import discord
from discord.ext import commands
from discord import ButtonStyle, Embed, ActionRow, Button, Color, Permissions
from discord.ui import View, Button
import asyncio
import os
import re
from datetime import datetime
import config  # Importar configuración RealTREM

# Configuración del bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuración global
COLORS = {
    'primary': Color.from_rgb(30, 144, 255),  # Azul
    'success': Color.from_rgb(76, 175, 80),
    'warning': Color.from_rgb(255, 152, 0),
    'error': Color.from_rgb(237, 66, 69),     # Rojo exacto para errores
    'info': Color.from_rgb(33, 150, 243)
}

# Emojis personalizados del servidor
CUSTOM_EMOJIS = {
    'microphone': '🎤',
    'volume': '🔊'
}

# Configuración RealTREM
VOICE_CHANNELS = config.AWAITING_CHANNELS  # Canales de espera
CHANNEL_NAMES = config.CHANNEL_NAMES
SERVER_CONFIG = config.SERVER_CONFIG
GAME_CHANNELS = config.GAME_CHANNELS

# Sistema de partidas activas
active_matches = {}  # {room_number: match_data}
room_data_messages = {}  # Para armazenar mensagens de dados da sala
captain_selections = {}  # Para seleção de capitanes

# Mapa de nombres de canales para exhibición
CHANNEL_NAMES = {
    '1447054233709838488': 'aguardando 1',
    '1447507397110140991': 'aguardando 2',
    '1447507470065991793': 'aguardando 3',
    '1447507531676123187': 'aguardando 4',
    '1447507587368091710': 'aguardando 5',
    '1447507703709696122': 'aguardando 6',
    '1447507785603485728': 'aguardando 7',
    '1447507869728772228': 'aguardando 8',
    '1447507925911474309': 'aguardando 9',
    '1447507992701309110': 'aguardando 10'
}

# Mapa para almacenar filas y mensajes de fila
queues = {}
queue_messages = {}

# Sistema de status dinámico del bot
bot_status = [
    '🎮 Dominando filas',
    '⚔️ Organizando partidas',
    '🚀 Conectando jugadores',
    '🏆 Gestionando Copa Star',
    '⭐ Creando experiencias'
]

# Vista para los botones de fila (Sistema RealTREM)
class QueueView(View):
    def __init__(self, user_queue_key):
        super().__init__(timeout=None)
        self.user_queue_key = user_queue_key
        self.game_mode = user_queue_key.split('_')[-1]  # Extraer game_mode del user_queue_key
        
        # Determinar si la fila está llena
        queue = queues.get(user_queue_key, {'players': [], 'teams': [[], []]})
        # Calcular máximo de jugadores basado en el modo
        if self.game_mode == '1v1':
            max_players = 2
        elif self.game_mode == '2v2':
            max_players = 4
        elif self.game_mode == '3v3':
            max_players = 6
        elif self.game_mode == '4v4':
            max_players = 8
        else:
            max_players = 2  # Default para casos no contemplados
        is_full = len(queue['players']) >= max_players
        is_closed = queues.get(f'{user_queue_key}_closed', False)
        
        # Botón Entrar (estilo RealTREM)
        current_players = len(queue['players'])
        label = f'Entrar na Fila [{current_players}/{max_players}]'
        if is_full or is_closed:
            self.add_item(Button(label=label, emoji='❌', style=ButtonStyle.secondary, disabled=True, custom_id=f'join_queue_{self.user_queue_key}'))
        else:
            self.add_item(Button(label=label, emoji='✅', style=ButtonStyle.success, disabled=False, custom_id=f'join_queue_{self.user_queue_key}'))
        
        # Botón Salir
        if is_closed:
            self.add_item(Button(label='Sair da Fila', emoji='❌', style=ButtonStyle.danger, disabled=True, custom_id=f'leave_queue_{self.user_queue_key}'))
        else:
            self.add_item(Button(label='Sair da Fila', emoji='❌', style=ButtonStyle.danger, disabled=False, custom_id=f'leave_queue_{self.user_queue_key}'))
        
        # Botón Cerrar (solo admin/creador)
        if is_full or is_closed:
            self.add_item(Button(label='Encerrar a Fila', emoji='🚫', style=ButtonStyle.secondary, disabled=True, custom_id=f'close_queue_{self.user_queue_key}'))
        else:
            self.add_item(Button(label='Encerrar a Fila', emoji='🚫', style=ButtonStyle.secondary, disabled=False, custom_id=f'close_queue_{self.user_queue_key}'))

    @discord.ui.button(label='Entrar na Fila', emoji='✅', style=ButtonStyle.success, disabled=False)
    async def join_button(self, interaction: discord.Interaction, button: Button):
        # El user_queue_key ya está en self
        await handle_queue_action(interaction, 'join', self.user_queue_key)

    @discord.ui.button(label='Sair da Fila', emoji='❌', style=ButtonStyle.danger, disabled=False)
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        # El user_queue_key ya está en self
        await handle_queue_action(interaction, 'leave', self.user_queue_key)

    @discord.ui.button(label='Encerrar a Fila', emoji='🚫', style=ButtonStyle.secondary, disabled=False)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        # El user_queue_key ya está en self
        await handle_queue_action(interaction, 'close', self.user_queue_key)

# Función para verificar si el usuario está en un canal de voz permitido
async def is_user_in_allowed_voice_channel(user):
    if not user.guild:
        return False
    
    member = await user.guild.fetch_member(user.id)
    if not member.voice or not member.voice.channel:
        return False
    
    channel_id = str(member.voice.channel.id)
    return channel_id in VOICE_CHANNELS

# Verificar si es creador del servidor
def is_creator(user_id):
    return config.is_creator(user_id)

# Verificar permisos
def has_permission(user, required_role='user'):
    """Verifica se o usuário tem permissão necessária"""
    if is_creator(user.id):
        return True
    
    # Verificar roles del usuario
    for role in user.roles:
        role_name = role.name.upper()
        if role_name in ['ADMIN', 'MODERADOR', 'SUPORTE', 'CAPITAO']:
            return True
    
    return False

# Función para buscar nombre del canal de voz
async def get_voice_channel_name(channel_id):
    try:
        channel = await bot.get_channel(int(channel_id))
        return channel.name if channel else 'Canal Desconocido'
    except:
        return 'Canal Desconocido'

# Detectar datos de sala (ID/contraseña)
async def detect_room_data(interaction):
    """Detecta dados de sala no último mensagem da thread"""
    try:
        # Buscar mensagens recentes na thread
        messages = []
        async for message in interaction.channel.history(limit=10):
            if message.author.id == interaction.user.id:
                messages.append(message)
                break
        
        if not messages:
            return None
            
        message_content = messages[0].content
        
        # Verificar se contém dados da sala
        room_data = config.detect_room_data(message_content)
        if room_data['found']:
            return room_data
            
        return None
    except Exception as e:
        print(f'Erro ao detectar dados da sala: {e}')
        return None

# Criar embed para dados da sala
async def create_room_data_embed(channel, room_number, room_data, players, team1, team2):
    """Cria embed com os dados da sala em formato RealTREM"""
    try:
        # Lista de jogadores
        player_list = '\n'.join([f'• {p["username"]}' for p in players])
        team1_list = '\n'.join([f'• {p["username"]}' for p in team1])
        team2_list = '\n'.join([f'• {p["username"]}' for p in team2])
        
        # Criar embed
        embed = Embed(
            color=COLORS['success'],
            title='✅ A SALA FOI CRIADA!',
            description=f"""📋 **Dados da sala para copiar:**

↪ **ID da Sala:** `{room_data['room_id']}`
↪ **Senha:** `{room_data['password']}`

👥 **Jogadores da partida #{room_number}:**
{player_list}

🎯 **Times:**
**Time 1:** {team1_list}
**Time 2:** {team2_list}

📌 **Mensagem fixada no canal da partida!**"""
        )
        
        # Botão para copiar ID e senha
        class CopyButton(View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(label='Copiar ID e Senha', emoji='📋', style=ButtonStyle.primary)
            async def copy_button(self, interaction: discord.Interaction, button: Button):
                await interaction.response.send_message(
                    '✅ **ID e Senha copiados com sucesso!**',
                    ephemeral=True
                )
        
        # Enviar embed com botão
        message = await channel.send(embed=embed, view=CopyButton())
        
        # Fixar mensagem
        try:
            await message.pin()
        except:
            pass  # Se não conseguir fixar, continuar
            
        return message
        
    except Exception as e:
        print(f'Erro ao criar embed de dados da sala: {e}')
        return None

# Movimento automático de jogadores
async def auto_move_players_to_game_channels(room_number, team1, team2):
    """Move automaticamente os jogadores para os canais de voz"""
    try:
        # Obter canais de destino
        time1_channel = await bot.get_channel(int(GAME_CHANNELS['time_1'][str(room_number)]))
        time2_channel = await bot.get_channel(int(GAME_CHANNELS['time_2'][str(room_number)]))
        
        if not time1_channel or not time2_channel:
            print('Erro: Canais de destino não encontrados')
            return False
            
        moved_count = 0
        
        # Mover jogadores do Team 1
        for player_data in team1:
            try:
                member = await bot.guilds[0].fetch_member(int(player_data['id']))
                if member and member.voice and member.voice.channel:
                    await member.move_to(time1_channel)
                    moved_count += 1
            except Exception as e:
                print(f'Erro ao mover jogador {player_data["username"]}: {e}')
                
        # Mover jogadores do Team 2  
        for player_data in team2:
            try:
                member = await bot.guilds[0].fetch_member(int(player_data['id']))
                if member and member.voice and member.voice.channel:
                    await member.move_to(time2_channel)
                    moved_count += 1
            except Exception as e:
                print(f'Erro ao mover jogador {player_data["username"]}: {e}')
                
        print(f'Movimento automático concluído: {moved_count} jogadores movidos')
        return moved_count > 0
        
    except Exception as e:
        print(f'Erro no movimento automático: {e}')
        return False

# Seleção de capitanes (futuro)
async def show_captain_selection(interaction, room_number, players):
    """Mostra menu de seleção de capitanes"""
    try:
        # Por enquanto, os capitanes são os primeiros jogadores de cada time
        # Implementação futura: menu interativo para seleção
        
        player_list = '\n'.join([f'• {p["username"]}' for p in players])
        
        embed = Embed(
            color=COLORS['info'],
            title='👑 **SELEÇÃO DE CAPITÃES**',
            description=f'👥 **Jogadores para selecionar:**\n{player_list}\n\n🎯 **Time 1 - Escolha 2 jogadores:**'
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        print(f'Erro ao mostrar seleção de capitanes: {e}')

# Función para verificar si el usuario ya está en alguna fila
def is_user_in_any_queue(user_id):
    user_id_str = str(user_id)
    for user_queue_key, queue in queues.items():
        # Verificar si el usuario es el creador de esta fila
        if user_queue_key.startswith(user_id_str + '_'):
            # Verificar si el usuario está en los jugadores de esta fila
            if any(p['id'] == user_id_str for p in queue['players']):
                return user_queue_key.split('_')[-1]  # Retornar el game_mode
    return None

# Función para crear embed de la fila
def create_queue_embed(user_queue_key, is_closed=False):
    # Extraer game_mode del user_queue_key (formato: "user_id_game_mode")
    game_mode = user_queue_key.split('_')[-1]  # Obtener la última parte después del último '_'
    queue = queues.get(user_queue_key, {'players': [], 'teams': [[], []]})
    is_full = len(queue['players']) >= (4 if game_mode == '2v2' else 2)
    is_empty = len(queue['players']) == 0
    
    if is_closed:
        status = '🚫 Cerrada com Sucesso!'
        description = 'Esta fila foi fechada com sucesso. Aguarde uma nova fila.'
    elif is_full:
        status = '🎯 Partida Iniciada!'
        description = 'Partida em andamento. Todos os jogadores devem ir para o canal de voz.'
    elif is_empty:
        status = '⏳ Aguardando Jogadores'
        description = f'Fila vazia para **{game_mode}**. Use os botões para entrar na fila.'
    else:
        status = '🔥 Fila Normal'
        description = f'Jogadores na fila: **{len(queue["players"])}/{4 if game_mode == "2v2" else 2}**'

    # Generar lista de jugadores con slots vacíos
    player_list = ''
    if game_mode == '2v2':
        team_a_players = [f'🔴 {p.get("username", f"<@{p["id"]}>")}' for p in queue['teams'][0]]
        team_b_players = [f'🔴 {p.get("username", f"<@{p["id"]}>")}' for p in queue['teams'][1]]
        
        # Llenar slots vacíos para Team A
        while len(team_a_players) < 2:
            team_a_players.append('🟢 Libre')
        
        # Llenar slots vacíos para Team B
        while len(team_b_players) < 2:
            team_b_players.append('🟢 Libre')
        
        player_list = f'**Equipo A ({len(queue["teams"][0])}/2):**\n{"\n".join(team_a_players)}\n\n**Equipo B ({len(queue["teams"][1])}/2):**\n{"\n".join(team_b_players)}'
    else:
        players = [f'🔴 {p.get("username", f"<@{p["id"]}>")}' for p in queue['players']]
        while len(players) < 2:
            players.append('🟢 Libre')
        player_list = f'**Jugadores ({len(queue["players"])}/2):**\n{"\n".join(players)}'

    # Color dinámico según el estado (estilo RealTREM)
    if is_closed:
        embed_color = COLORS['error']  # Rojo para cerrada
    elif is_full:
        embed_color = COLORS['success']  # Verde para llena
    else:
        embed_color = COLORS['primary']  # Azul para normal/vacía

    embed = Embed(
        color=embed_color,
        title=f'🎮 Copa Star - Fila {game_mode}',
        description=description
    )
    embed.add_field(name=status, value=player_list, inline=False)
    embed.set_footer(text='Bot Copa Star • Sistema RealTREM')
    embed.timestamp = datetime.utcnow()

    return embed

# Función para manejar acciones de cola
async def handle_queue_action(interaction, action, user_queue_key=None):
    user_id = str(interaction.user.id)
    username = interaction.user.name
    
    # Si no se pasa user_queue_key, extraerlo del custom_id (fallback)
    if not user_queue_key:
        game_mode = interaction.custom_id.split('_')[0] if '_' in interaction.custom_id else interaction.custom_id.replace('queue', '').strip('_')
        user_queue_key = f"{user_id}_{game_mode}"
    else:
        # Extraer game_mode del user_queue_key
        game_mode = user_queue_key.split('_')[-1]

    try:
        # Verificar si el usuario ya está en otra fila
        user_in_queue = is_user_in_any_queue(user_id)
        if user_in_queue and user_in_queue != game_mode:
            await interaction.response.send_message(
                f'❌ **¡Ya estás en la fila {user_in_queue}!**\n\nPrimero sal de la fila actual usando los botones o espera a que termine la partida.',
                ephemeral=True
            )
            return

        # Verificar si el usuario está en canal de voz permitido
        if action == 'join':
            in_voice_channel = await is_user_in_allowed_voice_channel(interaction.user)
            if not in_voice_channel:
                allowed_channels = []
                for channel_id in VOICE_CHANNELS:
                    channel_name = await get_voice_channel_name(channel_id)
                    allowed_channels.append(f'• {channel_name}')

                await interaction.response.send_message(
                    embed=Embed(
                        color=COLORS['error'],
                        description=f'❌ **¡No estás en ningún canal de voz permitido!**\n\n📢 **Canales permitidos:**\n{"\n".join(allowed_channels)}\n\n🎮 **Entra en un canal de voz e intenta de nuevo.**'
                    ),
                    ephemeral=True
                )
                return

        # Lógica para entrar en la fila
        if action == 'join':
            queue = queues.get(user_queue_key, {'players': [], 'teams': [[], []]})
            
            # Verificar si la fila está cerrada
            if queues.get(f'{user_queue_key}_closed'):
                await interaction.response.send_message(
                    '❌ **¡Esta fila está cerrada!**\n\nEspera a que se cree una nueva fila.',
                    ephemeral=True
                )
                return

            # Verificar si ya está en la fila
            if any(p['id'] == user_id for p in queue['players']):
                await interaction.response.send_message(
                    'ℹ️ **¡Ya estás en esta fila!**',
                    ephemeral=True
                )
                return

            # Calcular máximo de jugadores basado en el modo
            if game_mode == '1v1':
                max_players = 2
            elif game_mode == '2v2':
                max_players = 4
            elif game_mode == '3v3':
                max_players = 6
            elif game_mode == '4v4':
                max_players = 8
            else:
                max_players = 2  # Default para casos no contemplados

            # Verificar si la fila está llena (Mensaje RealTREM)
            if len(queue['players']) >= max_players:
                await interaction.response.send_message(
                    embed=Embed(
                        color=COLORS['error'],
                        title='ℹ️ ATENÇÃO',
                        description=f'Esta fila está lotada ({max_players}/{max_players}).\n↪ Provavelmente a partida está iniciando...'
                    ),
                    ephemeral=True
                )
                return

            # Agregar a la fila
            queue['players'].append({'id': user_id, 'username': username})
            
            # Lógica para 2v2 (dividir en equipos)
            if game_mode == '2v2':
                if len(queue['teams'][0]) < 2:
                    queue['teams'][0].append({'id': user_id, 'username': username})
                elif len(queue['teams'][1]) < 2:
                    queue['teams'][1].append({'id': user_id, 'username': username})

            queues[user_queue_key] = queue

            # Actualizar embed de la fila
            await update_queue_message(interaction.channel, user_queue_key)

            await interaction.response.send_message(
                embed=Embed(
                    color=COLORS['success'],
                    title='✅ SUCESSO',
                    description=f'Você entrou na fila com sucesso!\n↪ Aguarde a fila atingir {max_players} jogadores para iniciar a partida.'
                ),
                ephemeral=True
            )

            # Si la fila se llenó, iniciar partida
            if len(queue['players']) >= max_players:
                await start_match(interaction, game_mode, queue)

        # Lógica para salir de la fila
        elif action == 'leave':
            queue = queues.get(user_queue_key)
            if not queue:
                await interaction.response.send_message(
                    '❌ **¡Esta fila no existe!**',
                    ephemeral=True
                )
                return

            player_index = next((i for i, p in enumerate(queue['players']) if p['id'] == user_id), -1)
            if player_index == -1:
                await interaction.response.send_message(
                    'ℹ️ **¡No estás en esta fila!**',
                    ephemeral=True
                )
                return

            # Remover de la fila
            queue['players'].pop(player_index)
            
            # Remover de los equipos (para 2v2)
            if game_mode == '2v2':
                queue['teams'][0] = [p for p in queue['teams'][0] if p['id'] != user_id]
                queue['teams'][1] = [p for p in queue['teams'][1] if p['id'] != user_id]

            queues[user_queue_key] = queue

            # Actualizar embed de la fila
            await update_queue_message(interaction.channel, user_queue_key)

            await interaction.response.send_message(
                '👋 **¡Saliste de la fila con éxito!**',
                ephemeral=True
            )

        # Lógica para cerrar fila
        elif action == 'close':
            queues[f'{game_mode}_closed'] = True
            
            # Actualizar embed de la fila
            await update_queue_message(interaction.channel, game_mode)

            await interaction.response.send_message(
                '🚧 **¡Fila cerrada con éxito!**',
                ephemeral=True
            )

    except Exception as error:
        print('Error en la interacción:', error)
        await interaction.response.send_message(
            '❌ **Ocurrió un error al procesar tu solicitud.**',
            ephemeral=True
        )

# Función para actualizar mensaje de la fila
async def update_queue_message(channel, user_queue_key):
    try:
        message_id = queue_messages.get(user_queue_key)
        if message_id:
            message = await channel.fetch_message(message_id)
            is_closed = queues.get(f'{user_queue_key}_closed', False)
            
            await message.edit(
                embed=create_queue_embed(user_queue_key, is_closed),
                view=QueueView(user_queue_key)
            )
    except Exception as error:
        print('Error al actualizar mensaje de la fila:', error)

# Función para iniciar partida (Sistema RealTREM Completo)
async def start_match(interaction, game_mode, queue):
    try:
        # Obter número da sala
        room_number = config.get_available_room_number()
        
        # Criar thread para a partida
        thread = await interaction.channel.create_thread(
            name=f'🎮 Partida #{room_number} - {game_mode} - {datetime.now().strftime("%d/%m/%Y")}',
            type=discord.ChannelType.private_thread,
            invitable=False
        )

        # Dividir jogadores em times (estilo RealTREM)
        if game_mode == '2v2':
            team1 = queue['teams'][0]
            team2 = queue['teams'][1]
        else:  # 1v1
            team1 = [queue['players'][0]] if len(queue['players']) >= 1 else []
            team2 = [queue['players'][1]] if len(queue['players']) >= 2 else []

        # Mensaje público de sucesso (estilo RealTREM)
        team1_players = ', '.join([p['username'] for p in team1])
        team2_players = ', '.join([p['username'] for p in team2])
        
        await interaction.channel.send(
            embed=Embed(
                color=COLORS['success'],
                title='🎯 PARTIDA CRIADA COM SUCESSO!',
                description=f'✅ A partida **{game_mode}** #{room_number} foi criada com sucesso!\n\n🎮 **Canal da partida:** <#{thread.id}>\n👥 **Jogadores:** {len(queue["players"])}\n\n🔒 **Canais de voz criados:**\n🔒 #{room_number} - Time 1\n🔒 #{room_number} - Time 2\n\n⏰ **Data:** {datetime.now().strftime("%d/%m/%Y %H:%M")}'
            )
        )

        # MOVIMENTO AUTOMÁTICO (estilo RealTREM)
        move_success = await auto_move_players_to_game_channels(room_number, team1, team2)
        
        if move_success:
            # Mensaje de movimento automático
            await interaction.channel.send(
                config.REALTREM_MESSAGES['auto_move_success'].format(
                    room_number=room_number,
                    team1_players=team1_players,
                    team2_players=team2_players
                ),
                embed=Embed(
                    color=COLORS['success'],
                    title='✅ MOVIMENTAÇÃO AUTOMÁTICA REALIZADA!',
                    description=f'🎮 A partida #{room_number} foi criada com sucesso!\n\n👥 **Jogadores movidos:**\nTeam 1: {team1_players}\nTeam 2: {team2_players}\n\n🔒 **Canais criados:**\n🔒 #{room_number} - Time 1\n🔒 #{room_number} - Time 2'
                )
            )
        
        # Mensaje privado no thread com instruções (estilo RealTREM)
        player_list = '\n'.join([f'• {p["username"]}' for p in queue['players']])
        team1_list = '\n'.join([f'• {p["username"]}' for p in team1])
        team2_list = '\n'.join([f'• {p["username"]}' for p in team2])
        
        await thread.send(
            f'🎮 **Bem-vindos à partida #{room_number} - {game_mode}!**\n\n👥 **Jogadores confirmados:**\n{player_list}\n\n🎯 **Times:**\n**Time 1:** {team1_list}\n**Time 2:** {team2_list}\n\n📋 **Instruções:**\n1. ✅ Todos devem estar nos canais de voz correspondentes\n2. 🎯 Aguardem a criação da sala pelo Staff\n3. 📢 Para reportar problemas, mencionem @everyone\n\n🚀 **Que comecem os jogos!**',
            embed=Embed(
                color=COLORS['info'],
                title=f'🏆 Partida #{room_number} - Detalhes',
                fields=[
                    {'name': '🎮 Modo de Jogo', 'value': game_mode, 'inline': True},
                    {'name': '👥 Jogadores', 'value': str(len(queue['players'])), 'inline': True},
                    {'name': '🏷️ Partida #', 'value': str(room_number), 'inline': True},
                    {'name': '⏰ Criado em', 'value': datetime.now().strftime('%d/%m/%Y %H:%M'), 'inline': False},
                    {'name': '🔒 Canais', 'value': f'#{room_number} - Time 1 & #{room_number} - Time 2', 'inline': False}
                ]
            )
        )

        # Seleção de capitanes (futuro - por enquanto automático)
        if len(queue['players']) >= 4:  # Apenas para 2v2
            await show_captain_selection(interaction, room_number, queue['players'])

        # Armazenar dados da partida ativa
        active_matches[room_number] = {
            'thread_id': thread.id,
            'game_mode': game_mode,
            'players': queue['players'],
            'team1': team1,
            'team2': team2,
            'created_at': datetime.now(),
            'channel': interaction.channel
        }

        # Limpar fila
        queues.pop(game_mode, None)
        queue_messages.pop(game_mode, None)

    except Exception as error:
        print('Error al crear partida:', error)
        await interaction.channel.send(
            embed=Embed(
                color=COLORS['error'],
                title='❌ ERROR AL CREAR PARTIDA',
                description='Ocurrió un error al crear el canal de la partida. Inténtalo de nuevo.'
            )
        )

# Evento cuando el bot está listo
@bot.event
async def on_ready():
    print(f'🤖 {bot.user} está online!')
    
    # Cambiar status del bot
    status_index = 0
    async def update_status():
        nonlocal status_index
        while True:
            await bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.playing, name=bot_status[status_index]),
                status=discord.Status.online
            )
            status_index = (status_index + 1) % len(bot_status)
            await asyncio.sleep(30)  # Cambiar cada 30 segundos
    
    # Iniciar la tarea de cambio de status
    asyncio.create_task(update_status())

# Comando slash para crear fila
@bot.command(name="fila", description="Crear una nueva fila para partidas")
async def create_queue_slash(
    ctx,
    modo: str = "2v2"
):
    game_mode = modo.lower()
    
    # Verificar canal de voz
    in_voice_channel = await is_user_in_allowed_voice_channel(ctx.author)
    if not in_voice_channel:
        allowed_channels_list = '\n'.join([f'<#{id}>' for id in VOICE_CHANNELS])
        await ctx.send(
            embed=Embed(
                color=COLORS['error'],
                description=f'❌ **¡No estás en ningún canal de voz permitido!**\n\n📢 **Canales permitidos:**\n{allowed_channels_list}\n\n🎮 **Entra en un canal de voz e intenta de nuevo.**'
            )
        )
        return

    # Verificar si ya existe una fila activa para ESTE USUARIO
    user_queue_key = f"{ctx.author.id}_{game_mode}"
    if user_queue_key in queues and not queues.get(f'{user_queue_key}_closed'):
        await ctx.send(
            'ℹ️ **¡Ya tienes una fila activa!**\n\nUsa los botones en el mensaje de tu fila para participar.'
        )
        return

    # Crear nueva fila para ESTE USUARIO
    queues[user_queue_key] = {'players': [], 'teams': [[], []]}
    queues.pop(f'{user_queue_key}_closed', None)

    # Enviar embed de la fila
    queue_message = await interaction.response.send_message(
        embed=create_queue_embed(user_queue_key),
        view=QueueView(user_queue_key)
    )

    # Guardar referencia del mensaje
    # Guardar mensaje de la fila para ESTE USUARIO
    queue_messages[user_queue_key] = queue_message.id

    await interaction.followup.send(
        '✅ **¡Fila creada con éxito!**\n\nUsa los botones para gestionar la fila.',
        ephemeral=True
    )

# Comando de mensaje para crear fila
@bot.event
async def on_message(message):
    if not message.content.startswith('!') or message.author.bot:
        return

    args = message.content[1:].strip().split()
    command = args[0].lower() if args else ''

    if command == 'fila':
        game_mode = args[1].lower() if len(args) > 1 else '2v2'
        
        if game_mode not in ['1v1', '2v2', '3v3', '4v4']:
            await message.reply('❌ **¡Modo inválido!**\n\nUsa: `!fila 1v1`, `!fila 2v2`, `!fila 3v3` o `!fila 4v4`')
            return

        # Verificar canal de voz
        in_voice_channel = await is_user_in_allowed_voice_channel(message.author)
        if not in_voice_channel:
            allowed_channels_list = '\n'.join([f'<#{id}>' for id in VOICE_CHANNELS])
            await message.reply(
                embed=Embed(
                    color=COLORS['error'],
                    description=f'❌ **¡No estás en ningún canal de voz permitido!**\n\n📢 **Canales permitidos:**\n{allowed_channels_list}\n\n🎮 **Entra en un canal de voz e intenta de nuevo.**'
                )
            )
            return

        # Verificar si ya existe una fila activa para ESTE USUARIO
        user_queue_key = f"{message.author.id}_{game_mode}"
        if user_queue_key in queues and not queues.get(f'{user_queue_key}_closed'):
            await message.reply(
                'ℹ️ **¡Ya tienes una fila activa!**\n\nUsa los botones en el mensaje de tu fila para participar.'
            )
            return

        # Crear nueva fila para ESTE USUARIO
        queues[user_queue_key] = {'players': [], 'teams': [[], []]}
        queues.pop(f'{user_queue_key}_closed', None)

        # Enviar embed de la fila
        queue_message = await message.channel.send(
            embed=create_queue_embed(user_queue_key),
            view=QueueView(user_queue_key)
        )

        # Guardar referencia del mensaje
        # Guardar mensaje de la fila para ESTE USUARIO
        queue_messages[user_queue_key] = queue_message.id

        await message.reply('✅ **¡Fila creada con éxito!**\n\nUsa los botones para gestionar la fila.')

# Evento para detectar dados de sala (Sistema RealTREM)
@bot.event
async def on_message(message):
    # Ignorar mensagens do bot
    if message.author.bot:
        return
    
    # Processar comandos
    if message.content.startswith('!'):
        await handle_message_commands(message)
        return
    
    # DETECÇÃO DE DADOS DA SALA (estilo RealTREM)
    try:
        # Verificar se está em thread de partida
        if isinstance(message.channel, discord.Thread) and message.channel.type == discord.ChannelType.private_thread:
            # Detectar dados da sala
            room_data = config.detect_room_data(message.content)
            
            if room_data['found']:
                # Procurar partida ativa
                room_number = None
                match_data = None
                
                # Buscar partida pelo nome da thread
                thread_name = message.channel.name
                if 'Partida #' in thread_name:
                    try:
                        room_number = int(thread_name.split('Partida #')[1].split(' -')[0])
                        match_data = active_matches.get(room_number)
                    except:
                        pass
                
                if match_data and room_number:
                    # Criar embed com dados da sala
                    embed_message = await create_room_data_embed(
                        message.channel, 
                        room_number, 
                        room_data, 
                        match_data['players'],
                        match_data['team1'],
                        match_data['team2']
                    )
                    
                    if embed_message:
                        # Mensaje de sucesso (estilo RealTREM)
                        await message.channel.send(
                            embed=Embed(
                                color=COLORS['success'],
                                title='✅ DADOS DA SALA DETECTADOS!',
                                description=f'📋 Os dados da sala para a partida #{room_number} foram detectados e formatados automaticamente!'
                            )
                        )
                        
                        # Tag todos os jogadores
                        player_mentions = ' '.join([f'<@{p["id"]}>' for p in match_data['players']])
                        if player_mentions:
                            await message.channel.send(
                                f'👥 **{player_mentions}** - Dados da sala detectados!'
                            )
                            
    except Exception as e:
        print(f'Erro na detecção de dados da sala: {e}')

# Função para processar comandos de mensagem
async def handle_message_commands(message):
    """Processa comandos de mensagem"""
    if not message.content.startswith('!') or message.author.bot:
        return

    args = message.content[1:].strip().split()
    command = args[0].lower() if args else ''

    if command == 'fila':
        game_mode = args[1].lower() if len(args) > 1 else '2v2'
        
        if game_mode not in ['1v1', '2v2', '3v3', '4v4']:
            await message.reply('❌ **¡Modo inválido!**\n\nUsa: `!fila 1v1`, `!fila 2v2`, `!fila 3v3` o `!fila 4v4`')
            return

        # Verificar canal de voz
        in_voice_channel = await is_user_in_allowed_voice_channel(message.author)
        if not in_voice_channel:
            allowed_channels_list = '\n'.join([f'<#{id}>' for id in VOICE_CHANNELS])
            await message.reply(
                embed=Embed(
                    color=COLORS['error'],
                    description=f'❌ **¡No estás en ningún canal de voz permitido!**\n\n📢 **Canales permitidos:**\n{allowed_channels_list}\n\n🎮 **Entra en un canal de voz e intenta de nuevo.**'
                )
            )
            return

        # Verificar se já existe uma fila ativa para ESTE USUÁRIO
        user_queue_key = f"{message.author.id}_{game_mode}"
        if user_queue_key in queues and not queues.get(f'{user_queue_key}_closed'):
            await message.reply(
                'ℹ️ **¡Ya tienes una fila activa!**\n\nUsa los botones en el mensaje de tu fila para participar.'
            )
            return

        # Criar nova fila para ESTE USUÁRIO
        queues[user_queue_key] = {'players': [], 'teams': [[], []]}
        queues.pop(f'{user_queue_key}_closed', None)

        # Enviar embed da fila
        queue_message = await message.channel.send(
            embed=create_queue_embed(user_queue_key),
            view=QueueView(user_queue_key)
        )

        # Guardar referência da mensagem
        # Guardar mensaje de la fila para ESTE USUARIO
        queue_messages[user_queue_key] = queue_message.id

        await message.reply('✅ **¡Fila criada com sucesso!**\n\nUsa os botões para gerenciar a fila.')

# Iniciar el bot
if __name__ == "__main__":
    # Token de Discord del bot
    print("🔍 Checking environment variables...")
    print(f"All environment variables: {list(os.environ.keys())}")
    
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    print(f"DISCORD_TOKEN found: {'Yes' if DISCORD_TOKEN else 'No'}")
    print(f"Token length: {len(DISCORD_TOKEN) if DISCORD_TOKEN else 0}")
    
    if not DISCORD_TOKEN:
        print("❌ Error: DISCORD_TOKEN not found in environment variables")
        print("Please set the DISCORD_TOKEN environment variable")
        print("🔧 Available env vars containing 'DISCORD':")
        for key in os.environ:
            if 'DISCORD' in key.upper():
                print(f"  {key}: {os.environ[key][:20]}...")
        exit(1)
    
    print("🚀 DEPLOY ACTUALIZADO - Railway debe usar este código!")
    print("✅ Starting bot with token...")
    bot.run(DISCORD_TOKEN)