import json

from bs4 import BeautifulSoup
import pytest

from scripts.steam import parse_profile, render_card


def test_profile_reads_only_owner_and_recent_games():
    data = parse_profile('''<span class="actual_persona_name">Test &amp; Player</span>
      <div class="playerAvatarAutoSizeInner"><picture><img srcset="https://avatars.fastly.steamstatic.com/avatar.jpg"></picture></div>
      <div class="persona_level"><span class="friendPlayerLevelNum">11</span></div>
      <span class="friendPlayerLevelNum">99</span>
      <div class="profile_count_link"><a><span class="count_link_label">Games</span><span class="profile_count_link_total">1,234</span></a></div>
      <div class="recentgame_recentplaytime">14.5 hours past 2 weeks</div>
      <div class="favoritegame_showcase"><div class="value">9999</div><div>Hours played</div></div>
      <div class="recent_game"><div class="game_name"><a href="https://steamcommunity.com/app/123">Game &amp; Name</a></div>
      <img class="game_capsule" src="https://shared.fastly.steamstatic.com/cover.jpg"><div class="game_info_details">1,200.5 hrs on record</div></div>''')
    assert data['level'] == 11
    assert data['games'] == 1234
    assert data['badges'] is None
    assert data['recentHours'] == 14.5
    assert data['recentGames'][0]['hours'] == 1200.5
    assert data['avatar'].endswith('/avatar.jpg')
    assert 'totalHours' not in data  # Favorite-game hours must not become library totals.


def test_private_profile_does_not_invent_zero_counts():
    data = parse_profile('<span class="actual_persona_name">Private</span><p>This profile is private.</p>')
    assert data['recentGames'] == []
    assert data['games'] is None and data['recentHours'] is None
    assert data['status'] == 'unknown'
    with pytest.raises(ValueError):
        parse_profile('<h1>Service Unavailable</h1>')


@pytest.mark.parametrize('header,expected', [('Currently Offline', 'offline'), ('Currently Online', 'online'), ('Currently In-Game', 'in-game'), ('Currently Away', 'away')])
def test_status_and_current_game(header, expected):
    data = parse_profile(f'<span class="actual_persona_name">Player</span><div class="profile_in_game_header">{header}</div><div class="profile_in_game_name">Game &amp; Name</div>')
    assert data['status'] == expected
    assert data['currentGame'] == ('Game & Name' if expected == 'in-game' else '')


def test_render_escapes_text_and_omits_unknown_stats(tmp_path):
    data = parse_profile('<span class="actual_persona_name">&lt;script&gt;</span>')
    data['avatar'] = 'javascript:alert(1)'
    (tmp_path / '_data').mkdir()
    (tmp_path / '_data/steam.json').write_text(json.dumps(data))
    soup = BeautifulSoup(render_card(tmp_path), 'html.parser')
    assert soup.select_one('.steam-identity strong').get_text() == '<script>'
    assert not soup.select('script, img, .steam-stats dd')
    assert '游玩信息未公开' in soup.get_text()
    assert soup.select_one('time')['datetime'] == data['updatedAt']


def test_english_card_preserves_chinese_content_and_legacy_default(tmp_path):
    data = parse_profile('<span class="actual_persona_name">玩家</span>')
    data.update(status='in-game', currentGame='中文游戏')
    (tmp_path / '_data').mkdir()
    (tmp_path / '_data/steam.json').write_text(json.dumps(data))
    english = BeautifulSoup(render_card(tmp_path, lang='en'), 'html.parser')
    assert english.select_one('.about-steam')['data-ui-lang'] == 'en'
    assert english.select_one('.steam-status').get_text() == 'Playing 中文游戏'
    assert 'Playtime is private' in english.get_text()
    assert 'Snapshot at publication' in english.get_text()
    assert '正在玩 中文游戏' in BeautifulSoup(render_card(tmp_path), 'html.parser').get_text()
