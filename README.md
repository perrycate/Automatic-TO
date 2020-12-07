Half-finished code for a bot to run tournaments entirely through discord.

## Installation
0. Make sure you have a recent-ish version of Python 3 installed, and pip/pipenv. If you're using windows, ~~install linux~~ make sure you have [WSL Installed](https://docs.microsoft.com/en-us/windows/wsl/install-win10) and are running the commands from inside it.
1. From the directory the code is located in, install dependencies by running:

    pipenv install

2. Get a copy of your Challonge API Key from [here](https://challonge.com/settings/developer).

3. Follow the instructions to create a discord bot [here](https://discordpy.readthedocs.io/en/latest/discord.html), and copy your bot's token.

4. Start the bot with the following command:

    DISCORD_BOT_TOKEN=\<your token here\> pipenv run ./main.py

## Usage:
TODO. Speaking of which...

## How to contribute
Contributions are very welcome and encouraged! 
Contributions can take many forms, such as contributing documentation, reporting or diagnosing bugs, and of course, code contributions.

You can see a list of known bugs and planned features [in the issues tab](https://github.com/perrycate/discord-tournament-bot/issues).
If you have any questions about the code, how to contribute, or anything else, feel free to contact Perry Cate via the contact information on his [GitHub Profile](https://github.com/perrycate).

Here is a summary of the relevant files in the codebase as it currently stands:
 * **bracket.py**: Contains the logic for managing a bracket.
 * **d3thmatch.py**: Contains sample code for interacting with the Challonge API. Otherwise irrelevant.
 * **main.py**: Sets up the bot and manages interactions with discord.
 * **util.py**: Contains some handy utility functions.