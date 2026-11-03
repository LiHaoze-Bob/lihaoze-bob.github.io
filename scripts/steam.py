"""Refresh and render the public Steam profile snapshot; no API key is required."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

PROFILE = 'https://steamcommunity.com/profiles/76561199304157766/'
SNAPSHOT = Path(__file__).resolve().parents[1] / 'site-template/_data/steam.json'
MARKER = '<!-- steam-profile -->'


def steam_image(value: str) -> str:
    """Only embed images served by Steam, never arbitrary scraped URLs."""
    parsed = urlsplit(value)
    if parsed.scheme == 'https' and (parsed.hostname or '').endswith('.steamstatic.com'):
        return value
    return ''


def parse_profile(source: str) -> dict:
    soup = BeautifulSoup(source, 'html.parser')
    def text(selector):
        node = soup.select_one(selector)
        return node.get_text(' ', strip=True) if node else ''

    name = text('.actual_persona_name')
    if not name:
        raise ValueError('Steam did not return a profile; keep the previous snapshot.')
    avatar = soup.select_one('.playerAvatarAutoSizeInner > picture > img, .playerAvatarAutoSizeInner > img')
    avatar_url = steam_image((avatar.get('src') or avatar.get('srcset') or '') if avatar else '')
    level = text('.persona_level .friendPlayerLevelNum')
    status_header = text('.profile_in_game_header').lower()
    current_game = text('.profile_in_game_name')
    status = {
        'currently offline': 'offline', 'currently online': 'online',
        'currently in-game': 'in-game', 'currently away': 'away',
        'currently busy': 'busy', 'currently snooze': 'snooze',
        'looking to trade': 'trade', 'looking to play': 'play',
    }.get(status_header, 'unknown')
    counts = {}
    for link in soup.select('.profile_count_link a'):
        label, count = link.select_one('.count_link_label'), link.select_one('.profile_count_link_total')
        if label and count:
            number = count.get_text(strip=True).replace(',', '')
            if number.isdigit():
                counts[label.get_text(strip=True).lower()] = int(number)
    recent_hours = re.search(r'([\d,.]+) hours? past 2 weeks', text('.recentgame_recentplaytime'))
    games = []
    for game in soup.select('.recent_game')[:3]:
        link, image = game.select_one('.game_name a'), game.select_one('.game_capsule')
        if not link:
            continue
        appid = re.search(r'/app/(\d+)', link.get('href', ''))
        if not appid:
            continue
        details = game.select_one('.game_info_details')
        hours = re.search(r'([\d,.]+) hrs on record', details.get_text() if details else '')
        games.append({'name': link.get_text(strip=True), 'appid': appid[1],
                      'image': steam_image(image.get('src', '')) if image else '',
                      'hours': float(hours[1].replace(',', '')) if hours else None})
    # A private profile is a valid fresh snapshot: clear previously public game data.
    return {'profile': PROFILE, 'name': name, 'avatar': avatar_url,
            'status': status, 'currentGame': current_game if status == 'in-game' else '',
            'level': int(level) if level.isdigit() else None,
            'badges': counts.get('badges'), 'games': counts.get('games'),
            'recentHours': float(recent_hours[1].replace(',', '')) if recent_hours else None,
            'recentGames': games, 'updatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds')}


def render_card(template: Path, *, lang: str = 'zh-CN') -> str:
    path = template / '_data/steam.json'
    if not path.exists():
        return ''
    data = json.loads(path.read_text())
    config = template / '_data/steam-live.json'
    endpoint = json.loads(config.read_text()).get('endpoint', '') if config.exists() else ''
    if endpoint:
        parsed = urlsplit(endpoint)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Steam live endpoint must be an HTTPS URL without credentials, query or fragment.')
    def e(value):
        return escape(str(value), quote=True)
    date = datetime.fromisoformat(data['updatedAt']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%m-%d %H:%M')
    english = lang == 'en'
    def ui(en, zh):
        return en if english else zh
    labels = {'offline': '离线', 'online': '在线', 'in-game': '游戏中', 'away': '离开',
              'busy': '忙碌', 'snooze': '睡眠', 'trade': '想要交易', 'play': '想要玩游戏', 'unknown': '状态未公开'}
    if english:
        labels = {'offline': 'Offline', 'online': 'Online', 'in-game': 'In game', 'away': 'Away',
                  'busy': 'Busy', 'snooze': 'Snooze', 'trade': 'Looking to trade', 'play': 'Looking to play', 'unknown': 'Status is private'}
    status = data.get('status', 'unknown')
    if status not in labels:
        status = 'unknown'
    status_label = labels[status]
    if status == 'in-game' and data.get('currentGame'):
        status_label = ui('Playing ', '正在玩 ') + data['currentGame']
    status_html = f'<span class="steam-status" data-status="{status}" title="{ui('Status at collection time, not a live status', '采集时的状态，非实时在线状态')}">{e(status_label)}</span>'
    avatar = steam_image(data.get('avatar', ''))
    identity = (f'<img class="steam-avatar" src="{e(avatar)}" width="48" height="48" alt="" loading="lazy" />' if avatar else '')
    level = (f'<span class="steam-level">LV. {data["level"]}</span>' if data.get('level') is not None
             else '<span class="steam-level" hidden></span>')
    stats = ''.join(f'<div><dt>{label}</dt><dd>{data[key]}</dd></div>'
                    for key, label in [('badges', ui('Badges', '徽章')), ('games', ui('Games', '游戏'))] if data.get(key) is not None)
    recent = (f'{ui("Past two weeks: ", "近两周 ")}<strong>{data["recentHours"]:g}</strong>{ui(" hours", " 小时")}'
              if data.get('recentHours') is not None else ui('Playtime is private', '游玩信息未公开'))
    games = []
    for game in data.get('recentGames', []):
        image = steam_image(game.get('image', ''))
        hours = f'<span>{game["hours"]:g} h {ui("total", "总计")}</span>' if game.get('hours') is not None else ''
        cover = f'<img src="{e(image)}" width="184" height="69" alt="" loading="lazy" />' if image else ''
        games.append(f'<a class="steam-game" href="https://store.steampowered.com/app/{int(game["appid"])}/">'
                     f'{cover}<strong>{e(game["name"])}</strong>{hours}</a>')
    covers = '<div class="steam-recent" aria-label="' + ui('Recently played games', '最近玩的游戏') + '"' + ('' if games else ' hidden') + '>' + ''.join(games) + '</div>'
    return f'''<section class="about-steam" aria-labelledby="about-steam-title" data-steam-endpoint="{e(endpoint)}" data-ui-lang="{e(lang)}">
      <h2 id="about-steam-title">ON STEAM</h2>
      <p class="about-personal-note">I play GAMES.</p>
      <div class="steam-card">
        <div class="steam-header">
          <a class="steam-identity" href="{PROFILE}">{identity}<div><strong>{e(data['name'])}</strong>{level}{status_html}</div></a>
          <dl class="steam-stats">{stats}</dl>
        </div>
        <p class="steam-playtime">{recent}</p>
        {covers}
        <div class="steam-footer"><div class="steam-updates"><span class="steam-status-updated">{ui('Status collected at', '状态采集于')} <time datetime="{e(data['updatedAt'])}" title="{ui('Asia/Shanghai', '北京时间')}">{date} CST</time></span><span class="steam-stats-updated">{ui('Profile collected at', '资料采集于')} <time datetime="{e(data['updatedAt'])}" title="{ui('Asia/Shanghai', '北京时间')}">{date} CST</time></span><span class="steam-refresh" role="status">{ui('Snapshot at publication', '发布时的快照')}</span></div><a href="{PROFILE}">{ui('Steam profile', 'Steam 主页')} <span aria-hidden="true">↗</span></a></div>
      </div>
    </section>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, help='Parse a previously fetched public profile.')
    args = parser.parse_args()
    try:
        if args.html:
            source = args.html.read_text()
        else:
            request = Request(PROFILE + '?l=english', headers={'User-Agent': 'sychostar-notes-site/1.0'})
            with urlopen(request, timeout=20) as response:
                source = response.read(2_000_000).decode('utf-8')
        data = parse_profile(source)
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        temporary = SNAPSHOT.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(SNAPSHOT)
        print('Steam public profile snapshot refreshed.')
    except (OSError, ValueError) as exc:
        if not SNAPSHOT.exists():
            raise
        print(f'Steam refresh unavailable; using the dated saved snapshot: {exc}')


if __name__ == '__main__':
    main()
