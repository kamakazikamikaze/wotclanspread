from argparse import ArgumentParser
from datetime import datetime
import gspread
from json import dump, load
import multiprocessing
from oauth2client.service_account import ServiceAccountCredentials
import requests
from sys import exit

try:  # 2to3
    range = xrange
except NameError:
    pass


def create_config(filename):
    config = {
        'pool size': 20,
        'lang': 'en',
        'platform': 'xbox',
        'api key': 'demo',
        'clan name': 'RDDT',
        'sheet name': 'RDDT Member Tanks',
        'oauth creds': 'drive_oauth.json',
        'email': 'youremail@gmail.com'
    }
    with open(filename, 'w') as f:
        dump(config, f, indent=2)


def load_config(filename):
    with open(filename) as f:
        return load(f)


def get_clanid(url, params):
    '''
    Retrieve a clan ID number by searching with its tag

    Tag must be an _exact_ match

    :param string url: URL of the WG API
    :param dict params: Dictionary containing the following:
                        'application_id': str; API key/Application ID
                        'search': str; clan tag
                        Optional:
                        'language': str; see API documentation for accepted
                        fields

    :returns: Clan ID
    :rtype: int
    '''
    # return [j['clan_id'] for j in requests.get(url,
    # params=params).json()['data'] if j['tag'] == params['search']][0]
    try:
        attempts = 1
        while attempts <= 3:
            try:
                return filter(
                    lambda clan: clan['tag'] == params['search'],
                    requests.get(url, params=params, timeout=10).json()['data']
                )[0]['clan_id']
            except IndexError:
                attempts += 1
        raise IndexError
    except IndexError:
        raise ValueError('Clan tag could not be found!')


def get_players(url, params):
    '''
    Retrieve a list of all players from a clan

    :param string url: URL of the WG API
    :param dict params: Dictionary containing the following:
                        'application_id': str; API key/Application ID
                        'clan_id': int; clan ID
                        'fields': list('members_count', 'members_ids',
                                  'members.account_name')
                        'extra': list('members')
                        Optional:
                        'language': str; see API documentation for accepted
                                    fields

    :returns: All registered players with ID and name
    :rtype: tuple(str, str)
    '''
    return [
        (int(num),
         name['account_name']
         ) for num, name in requests.get(
            url,
            params=params,
            timeout=10
        ).json()['data'][str(clan_id)]['members'].iteritems()
    ]


def get_player_tanks(url, params, playername, queue=None,
                     account_id=None, access_token=None, in_garage=None):
    '''
    Retrieve a list of tanks (by ID) that a player has owned and/or used

    This method is designed for multiprocessing/multithreading to improve
    performance, especially for large clans. As such, the parameters are
    slightly different than other methods. However, you may still pass in the
    'account_id' field in `params` if desired.

    .. note: You may optionally filter tanks by their availability in the
             garage, however it requires a player's access token (login key) to
             do so. This may be passed in with the `params` parameter or as an
             optional parameter.

    :param string url: URL of the WG API
    :param dict params: Dictionary containing the following:
                        'application_id': str; API key/Application ID
                        'fields': list:('tank_id')
                        Optional:
                            'account_id': int; target player ID (if not
                                          multiprocessing)
                            'in_garage': str; '1' for filter if in player
                                         garage, or '0' for those absent
                            'language': str; see API documentation for accepted
                                        fields
    :param Queue queue: Multiprocessing queue to put data on, if
                        multiprocessing
    :param str playername: Player's account name
    :param int account_id: Player's WG account number
    :param str access_token: Temporary access token from a player's login;
                             required if filtering availability
    :param str in_garage: Filter ('0') for tanks absent from garage, or ('1')
                          available
    :returns: Player's tanks
    :rtype: tuple(str, list(int))
    '''
    if not account_id and 'account_id' not in params:
        raise ValueError('"account_id" not specified!')
    if account_id:
        params['account_id'] = int(account_id)
    for param, val in (('access_token', access_token),
                       ('in_garage', in_garage)):
        # Don't overwrite values passed in via `params`
        if val:
            # NoneTypes are ignored by Requests when constructing the URL
            params.update({param: val})
    # Tuple(player name, list(tanks by id))
    tanks = (playername, map(
        lambda tank: tank['tank_id'],
        # API requires 'account_id' as an int, but returns as a string. Why?!
        requests.get(
            url,
            params=params,
            timeout=10).json()['data'][str(params['account_id'])]))
    if queue:
        queue.put(tanks)
        return
    # If a queue is not being used, return the tuple
    return tanks


def get_tank_info(url, params, tank_id, queue=None):
    '''
    Retrieve tank information

    :param str url: API endpoint
    :param dict params: Dictionary containing the following:
                        'application_id': str; API key/Application ID
                        'fields': list; any desired information fields
                        Optional:
                        'language' str; response language
    :param tank_id: All desired tanks (limit 100)
    :param Queue queue: Queue to place results in, if multithreading
    :type tank_id: list(int or str)
    :returns: Tank information
    :rtype: dict
    '''
    params['tank_id'] = ','.join(map(str, tank_id))
    data = requests.get(url, params=params, timeout=10).json()['data']
    if queue:
        queue.put(data)
        return
    return data


def get_player_last_battle(url, params):
    '''
    Retrieve last battle time for each player

    :param str url: API endpoint to query
    :param dict params: Dictionary containing the following:
                        'application_id': str; API key/Application ID
                        'account_id': list(str); Player ID(s) to request data for

    '''
    return requests.get(url, params=params, timeout=15).json()['data']


if __name__ == '__main__':

    parser = ArgumentParser('Clan tank spreadsheet generator')
    parser.add_argument(
        'config',
        help='Configuration file. Must contain a JSON')
    parser.add_argument(
        '-g',
        '--generate-config',
        action='store_true',
        default=False,
        help='Create a smaple JSON configuration file')

    args = parser.parse_args()
    if args.generate_config:
        create_config(args.config)
        exit(0)

    config = load_config(args.config)
    apikey = config['api key']
    lang = config['lang']
    clan_name = config['clan name']
    platform = config['platform']
    if platform not in ('xbox', 'ps4'):
        raise Exception('Platform may only be "xbox" or "ps4"')
    pool_size = config['pool size']
    url = 'https://api-{}-console.worldoftanks.com/wotx'.format(platform)

    # Fetch clan ID, in case it changes in the future
    clan_search_url = '{}{}'.format(url, '/clans/list/')
    clan_search_params = dict()
    clan_search_params['language'] = lang
    clan_search_params['application_id'] = apikey
    clan_search_params['search'] = clan_name

    clan_id = get_clanid(clan_search_url, clan_search_params)

    # Fetch all members by name and ID
    clan_member_info_url = '{}{}'.format(url, '/clans/info/')
    clan_member_info_params = dict()
    clan_member_info_params['language'] = lang
    clan_member_info_params['application_id'] = apikey
    clan_member_info_params['clan_id'] = clan_id
    clan_member_info_params['fields'] = [
        'members_count', 'members_ids', 'members.account_name']
    clan_member_info_params['extra'] = ['members']

    members = get_players(clan_member_info_url, clan_member_info_params)

    member_tanks_url = '{}{}'.format(url, '/tanks/stats/')
    member_tanks_params = dict()
    member_tanks_params['language'] = lang
    member_tanks_params['application_id'] = apikey
    member_tanks_params['fields'] = ['tank_id']

    member_last_battle_url = '{}{}'.format(url, '/account/info/')
    member_last_battle_params = dict()
    member_last_battle_params['language'] = lang
    member_last_battle_params['application_id'] = apikey
    member_last_battle_params['account_id'] = ','.join(
        map(lambda p: str(p[0]), members))
    # member_last_battle_params['fields'] = ['last_battle_time', 'nickname']
    member_last_battle_params['fields'] = 'last_battle_time,nickname'
    battle_times = get_player_last_battle(
        member_last_battle_url, member_last_battle_params)

    # Fetch *all* tanks owned/used by players. Can be costly in performance,
    # so we'll try some asynchronous processing
    pool = multiprocessing.Pool(processes=pool_size)
    responses = multiprocessing.Manager().Queue()
    for playerid, playername in members:
        result = pool.apply_async(get_player_tanks,
                                  (member_tanks_url,
                                   member_tanks_params,
                                   playername,
                                   responses,
                                   playerid))
    pool.close()
    pool.join()
    player_tanks = {}
    tank_ids = set()
    while not responses.empty():
        player_results = responses.get()
        # player_results is a Tuple(playername, List[tanks])
        player_tanks.update({player_results[0]: player_results[1]})
        tank_ids.update(player_results[1])

    pool = multiprocessing.Pool(processes=pool_size)
    responses = multiprocessing.Manager().Queue()

    tank_info = {}
    tank_info_url = '{}{}'.format(url, '/encyclopedia/vehicles/')
    tank_info_params = dict()
    tank_info_params['language'] = lang
    tank_info_params['application_id'] = apikey
    tank_info_params['fields'] = ','.join(
        ['short_name', 'type', 'tier', 'is_premium'])
    for tanks in [tuple(tank_ids)[i:i + 100]
                  for i in range(0, len(tank_ids), 100)]:
        result = pool.apply_async(
            get_tank_info, (tank_info_url, tank_info_params, tanks, responses))

    pool.close()
    pool.join()

    while not responses.empty():
        tank_info.update(responses.get())

    # Send to Google Spreadsheets
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        config['oauth creds'], scope)

    gc = gspread.authorize(credentials)

    try:
        wb = gc.open(config['sheet name'])
    except gspread.SpreadsheetNotFound:
        # print 'Creating spreadsheet'
        wb = gc.create(config['sheet name'])
        wb.share(config['email'], perm_type='user', role='writer')
        wb.sheet1.update_title('Summary')
        wb.add_worksheet('Search', 1000, 4)
        wb.add_worksheet('Tank info', 1000, 5)
        wb.add_worksheet('Player info', 100, 2)
        wb.add_worksheet('Raw Ownership', 1000, 2)
        wb.add_worksheet('Last Player Battle', 100, 2)

    ws = wb.worksheet('Tank info')
    tank_type = {
        'lightTank': 'Light',
        'mediumTank': 'Medium',
        'heavyTank': 'Heavy',
        'AT-SPG': 'Tank Destroyer',
        'SPG': 'Artillery'
    }

    ws.resize(len(tank_info) + 1)
    cells = ws.range(1, 1, len(tank_info) + 1, 5)
    it = iter(cells)
    it.next().value = 'Name'
    it.next().value = 'Tier'
    it.next().value = 'Premium'
    it.next().value = 'Class'
    it.next().value = 'ID'
    try:
        for tank_id, tank_data in sorted(tank_info.iteritems()):
            try:
                it.next().value = tank_data['short_name']
                it.next().value = tank_data['tier']
                it.next().value = tank_data['is_premium']
                it.next().value = tank_type[tank_data['type']]
                it.next().value = int(tank_id)
            except TypeError:
                cur = it.next()
                while cur.col != 5:
                    cur.value = 'MISSINGNO.'
                    cur = it.next()
                cur.value = int(tank_id)
    except StopIteration:
        pass

    ws.update_cells(cells)

    ws = wb.worksheet('Raw Ownership')
    tank_total = sum([len(value) for value in player_tanks.values()])
    ws.resize(tank_total + 1)
    cells = ws.range(1, 1, tank_total + 1, 2)
    it = iter(cells)
    it.next().value = 'Player Name'
    it.next().value = 'Tank ID'
    try:
        for player_name, tanks in sorted(
                player_tanks.iteritems(), key=lambda s: s[0].lower()):
            for tank in tanks:
                it.next().value = player_name
                it.next().value = tank
    except StopIteration:
        pass

    ws.update_cells(cells)

    ws = wb.worksheet('Search')
    tank_total = sum([len(value) for value in player_tanks.values()])
    ws.resize(tank_total + 1)
    cells = ws.range(1, 1, tank_total + 1, 4)
    it = iter(cells)
    it.next().value = 'Tank'
    it.next().value = 'Tier'
    it.next().value = 'Premium'
    it.next().value = 'Owner'
    try:
        for player_name, tanks in sorted(
                player_tanks.iteritems(), key=lambda s: s[0].lower()):
            for tank in tanks:
                try:
                    tank_data = tank_info[str(tank)]
                    it.next().value = tank_data['short_name']
                    it.next().value = tank_data['tier']
                    it.next().value = tank_data['is_premium']
                    it.next().value = player_name
                except TypeError:
                    #                    print 'Damned `null` values'
                    cur = it.next()
                    while cur.col != 4:
                        cur.value = 'MISSINGNO.'
                        cur = it.next()
                    cur.value = player_name
    except StopIteration:
        pass

    ws.update_cells(cells)

    ws = wb.worksheet('Player IDs')
    ws.resize(len(members) + 1)
    cells = ws.range(1, 1, len(members) + 1, 2)
    it = iter(cells)
    it.next().value = 'Player Name'
    it.next().value = 'Player ID'
    try:
        for player_id, player_name in sorted(
                members, key=lambda s: s[1].lower()):
            it.next().value = player_name
            it.next().value = player_id
    except StopIteration:
        pass

    ws.update_cells(cells)

    ws = wb.worksheet('Last Player Battle')
    ws.resize(len(members) + 1)
    cells = ws.range(1, 1, len(members) + 1, 2)
    it = iter(cells)
    it.next().value = 'Player Name'
    it.next().value = 'Days since last battle'
    try:
        for _, player in sorted(battle_times.iteritems(),
                                key=lambda p: p[1]['nickname'].lower()):
            it.next().value = player['nickname']
            it.next().value = (
                datetime.utcnow() -
                datetime.utcfromtimestamp(
                    player['last_battle_time'])).days
    except StopIteration:
        pass

    ws.update_cells(cells)
