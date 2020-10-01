# Manages state of a tournament being run from within a discord server ("guild").
class Tournament:
    def __init__(self, guild_id, channel_id, msg_id):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.registration_message_id = msg_id
