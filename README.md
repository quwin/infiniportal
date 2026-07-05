# Infiniportal

**A Discord-native community management tool for Pixels.xyz guilds, players, and servers.**

Infiniportal helps Pixels communities look up player profiles, manage guild leaderboards, verify linked accounts, assign Discord roles, and coordinate in-game tasks — all from inside Discord.

> Built for Pixels.xyz communities that want cleaner onboarding, better guild visibility, and lightweight automation without making members leave Discord.

<img width="716" height="439" alt="website_ss" src="https://github.com/user-attachments/assets/cd25d3ee-4158-47c7-bdc1-25a097b7cdb8" />

---

## What Is Infiniportal?

Infiniportal is a Discord bot and web companion for Pixels.xyz communities.

It gives server owners and guild leaders a simple way to:

* Look up Pixels player profiles
* View global and guild-specific leaderboards
* Connect Discord users to Pixels accounts
* Verify wallet-linked accounts through Collab.Land
* Automatically assign Discord roles based on Pixels guild data
* Create and manage community tasks

The goal is to make Pixels community management easier, more transparent, and less manual.

---

## Why Use It?

Pixels guilds often need to answer the same questions over and over:

* Who is this player?
* What is their Pixels profile?
* Are they in our guild?
* What role should they have?
* Who are our top players?
* What tasks are available for members?

Infiniport.al brings those workflows into Discord with slash commands, buttons, embeds, and server-specific settings.

---

## Core Features

<img src="examples/command_list.png" width="400" height="400">

### Player Lookup

Search for a Pixels player by username, user ID, or wallet address.

Useful for checking player profiles, skill progress, and linked account information quickly from Discord.

```md
/lookup
```

<img src="examples/account_lookup.png" width="400" height="400">

---

### Guild/Global Leaderboards

View rankings for your assigned Pixels guild, as well as global rankings, directly in Discord.

Leaderboards can be filtered by skill, total level, and experience.

```md
/leaderboard
/global_leaderboard
```
<img src="examples/guild_leaderboard.png" width="400" height="400">
<img src="examples/global_leaderboard.png" width="400" height="400">
---

### Account Linking

Members can connect their Pixels accounts using a Collab.Land-powered flow.

Infiniport.al uses linked wallet information to verify account ownership and associate Discord users with Pixels accounts.

<img src="examples/link_account.png" width="400" height="400">

---

### Role Automation

Server admins can configure Discord roles based on Pixels-related requirements.

Examples:

* Guild Admin
* Guild Worker
* Guild Member
* Shard Pledger
* Shard Owner

This helps communities gate channels, permissions, or recognition roles using Pixels guild data.

---

### Community Taskboard

Members can post, claim, update, bump, and close tasks.

This is useful for guild work, item requests, community coordination, and reward-based player tasks.

```md
/task create
/taskboard
```

---

## How It Works

### 1. Add Infiniportal to Your Server

Invite the bot to your Discord server [using this link](https://discord.com/oauth2/authorize?client_id=1233991850470277130&scope=bot&permissions=1342598160) and grant the required permissions.

Recommended permissions:

* View Channels
* Send Messages
* Manage Messages
* Manage Channels
* Manage Roles
* Embed Links
* Use Application Commands

---

### 2. Configure Your Server

After setup, Infiniportal creates a private configuration area for server admins.

From there, admins can:

* Assign a Pixels guild
* Configure role rules
* View command information
* Manage server-specific settings

---

### 3. Let Members Connect Their Accounts

Members connect their Pixels account through the Discord account-linking flow.

Infiniportal does not ask for private keys, seed phrases, or transactions.

---

### 4. Use Commands in Discord

Once configured, your community can use Infiniportal directly through slash commands.

Popular commands:

```md
/lookup
/leaderboard
/global_leaderboard
/task create
/taskboard
```

---

## Security & Privacy

Infiniportal is designed around read-only verification.

It will never ask users for:

* Seed phrases
* Private keys
* Token approvals
* Wallet signatures for transactions
* Direct payments

Account verification is handled through Collab.Land, and the bot only uses the linked account data needed to verify Pixels ownership and assign server roles.

---

## Roadmap

Planned improvements include:

* Improved web dashboard
* More role requirement types
* Better guild analytics
* Expanded taskboard controls
* Cleaner onboarding flow
* Additional Pixels account and land-related views

---

## Contributing

Contributions, bug reports, and feature suggestions are welcome.

Good areas to contribute:

* UI/UX improvements
* Discord command polish
* Documentation
* Role automation logic
* Web dashboard features
* Error handling and setup flow

---

## Links

* Website: https://infiniportal.quwin.dev
* Discord: [Add invite link here](https://discord.com/oauth2/authorize?client_id=1233991850470277130&scope=bot&permissions=1342598160)
