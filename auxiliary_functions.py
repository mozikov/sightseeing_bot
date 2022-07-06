from json import JSONDecodeError
import random
import requests
import pandas as pd
import re
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderQueryError, GeocoderUnavailable
from geopy.adapters import AdapterHTTPError
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from time import sleep


# this is a class to work with SQLalchemy
Base = declarative_base()
class User(Base):
    __tablename__ = 'bot_users'
    user_id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    user_name = Column(String)
    first_msg_date = Column(String)
    msg_date = Column(String)
    lucky_query_counter = Column(Integer)
    text_query_counter = Column(Integer)
    def __repr__(self):
        a1 = f"<User(user_id='{self.user_id}', chat_id='{self.chat_id}', user_name='{self.user_name}',\n"
        a2 = f"first_msg_date='{self.first_msg_date}',msg_date='{self.msg_date}',\n"
        a3 = f"luckys='{self.lucky_query_counter}',texts='{self.text_query_counter}')>"
        return a1 + a2 + a3


#auxiliary functions 


# calculates random coords
def lucky_coords(long_south=35, long_north=50, latt_west=55, latt_east=60):
    lon = random.randint(long_south, long_north) + random.random()
    lat = random.randint(latt_west, latt_east) + random.random()
    return (lat, lon)


# Nominatium geocoder of adress with error handlers
def get_coords(adress):
    url = "http://nominatim.openstreetmap.org/reverse?email=\
        your_email_&format=xml&lat=-23.56320001&lon=\
        -46.66140002&zoom=27&addressdetails=1"
    try:
        geolocator = Nominatim(user_agent=url)
        location = geolocator.geocode(adress)
        #print(location.address)
        return (location.latitude, location.longitude, location.address)
    except (AttributeError or ConnectionError):
        return None
    except (GeocoderQueryError or AdapterHTTPError):
        print('WARNING: The length of a message exceeds Nominatim limit')
        return None
    except GeocoderUnavailable:
        return None

    
# parcer of geo coords
def coords_matcher(s: str):
    pattern = r'^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?)[,;]?\s*[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$'
    try:
        ans = re.match(pattern, s)
        return re.split('; |, |\*|\n| ', ans[0])
    except Exception:
        return None


# function to interact with openstreets map
def data_requester(lat_inp, lon_inp, dist_inp=1000, key_inp='tourism'):
    """
    dist_inp - radius of search
    key_inp - key (to add more info use key 'amenity')
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = """
                    [out:json][timeout:25];
                    (
                    node(around:{dist},{lat},{lon})[{key}];
                    );
                    out body;
                    """
    filled_query=overpass_query.format(dist=dist_inp, lat=lat_inp, lon=lon_inp, key=key_inp)    
    response = requests.get(overpass_url,
                            params={'data': filled_query})
    # in case of overflowing the API limits we get different input and catch JSONDecodeError
    try:
        data = response.json()
    except JSONDecodeError:
        return "Sorry, friend! I got too much queries. Could you, please, wait a while?"
    dataframe = pd.DataFrame.from_dict(data['elements'])
    ans = str()

    # our iterable consits of bunch of JSON tags
    for row in range(len(dataframe)):
        ptype = dataframe.iloc[row]['tags'][key_inp]
        # we don't need an information tag
        if ptype == 'information':
            break
        # nor we need an unnamed obgects tag (e.g. trash can) 
        try:
            pname = dataframe.iloc[row]['tags']['name']
        except KeyError:
            break
        # if obgect doesn't have web or wiki - just left the place empty
        try:
            pweb = dataframe.iloc[row]['tags']['website']
        except KeyError:
            pweb = ''
        try:
            pwiki = 'https://www.wikidata.org/wiki/' + dataframe.iloc[row]['tags']['wikidata']
        except KeyError:
            pwiki = ''    
        ans += f'{row}. {ptype} "{pname}" {pweb} {pwiki}\n'
    return ans


# func to write info about our queries
def write_to_db(message, type_of_query=None, url='sqlite:///bot_users.db'):
    """
    Writes info about queries
    Counts amount of lucky and text queries
    Returns info about user in case of stats type_of_query
    Tracks first and last msg dates
    In case of new user - adds info to DB
    """
    engine = create_engine(url, echo=False)   
    Session = sessionmaker(bind=engine)
    session = Session()

    our_user = session.query(User).filter_by(chat_id=message.chat.id).first() 
    if our_user:
        our_user.msg_date=message.date
        if type_of_query == 'lucky':
            our_user.lucky_query_counter += 1
        elif type_of_query == 'text':
            our_user.text_query_counter += 1
        elif type_of_query == 'stats':
            print(f'\n\nExecuting stats request,\n{our_user}')
            return our_user
        print(f'\n\nExecuting update query, type={type_of_query}\n{our_user}')
    else:
        new_user = User(user_id=message.from_user.id,
                        chat_id=message.chat.id,
                        user_name=message.from_user.full_name,
                        first_msg_date=message.date,
                        msg_date=message.date,
                        lucky_query_counter = 0,
                        text_query_counter = 0)
        session.add(new_user)
        print(f'\n\nExecuting add query, type={type_of_query}\n', new_user)
    session.commit()


# just returns proper msg according to data 
def user_stats(data):
    luckys = data.lucky_query_counter
    texts = data.text_query_counter
    replys = [
        "I don't know much about you yet, but I'm sure we are going to have a nice time!",
        "I'm sure I've seen you before! Let me tell something about you\n" +\
        f"You do feel yourself lucky! (You did {luckys} /lucky queries)\n" +\
        "Just a minor remark:\n" +\
        f"also you did {texts} text queries",
        "I'm sure I've seen you before! Let me tell something about you\n" +\
        f"You do know what you want! (You did {texts} text queries)\n" +\
        "Just a minor remark:\n" +\
        f"also you did {luckys} /lucky queries"
    ]
    if not(luckys or texts):
        return replys[0]
    elif luckys > texts:
        return replys[1]
    else:
        return replys[2]


# processes lucky query
async def process_lucky_query(lat, lon, message, bot):
    reply_messages = ["It's not a card game but I'm sure you'll have luck in love)",
                      "But may be it is a luck - finally you have a quiet pcace)",
                      "Anyways, thank's for request)",
                    ]
    # try to find adress of the place
    # Catch TypeError (e.g. it's a middle of an ocean)
    try:
        adress = get_coords(f'{lat}, {lon}')[2]
        adress_text = f'\nWe are going to {adress}'
        await bot.send_message(message.chat.id, adress_text)
    except TypeError:
        adress_text = f"I even don't know where are we going!"
        await bot.send_message(message.chat.id, adress_text)
    # search for sightseengs
    sightseengs = data_requester(lat, lon, dist_inp=6000)
    if not sightseengs:
        ans2 = "\nEghh... But actually there is nothing to see!\
            \nI'l look for some amenities then..."
        await bot.send_message(message.chat.id, ans2)
        sightseengs = data_requester(lat, lon, dist_inp=10000, key_inp='amenity')
        # If we didn't find anything - generate a polite reply
        if not sightseengs:
            sightseengs = "Well... Again nothing...\n"
            rn_int = random.randint(0, 10)
            if rn_int >= 5:
                sightseengs += random.choice(reply_messages)
    ans3 = sightseengs
    await message.answer(ans3)
    sleep(1)


# processes text query
async def process_query(lat, lon, message, bot):
        final_messages = ['Something else, friend?',
                          'Is that all?',
                          'What else can I do for you?',
                          ]

        # Reply with given coords and run API request to openstreetmaps
        ans = f"Fine! Your coordinates are {float(lat):.2f}, {float(lon):.2f}\nLet me look around ...\
            \nI'll answer in a few seconds)\n"
        await bot.send_message(message.chat.id, ans)

        # Try to find sth in 1km or 4 km vicinity 
        sightseengs = data_requester(lat, lon, dist_inp=4000)
        if not sightseengs:
            sightseengs = '\nEghh... But actually there is nothing to see ('
        
        # send data of the request and give one of polite finishings 
        await bot.send_message(message.chat.id, sightseengs)
        await message.answer(random.choice(final_messages))
        sleep(1)


# just returns start msg
def get_start_msg(full_name):
    msg = f"Hi, {full_name}!\nI'll help you to look around a little!\
    \nJust tell me coordinates or adress)\
    \n1.You can send me an adress (please, write city name explicitly)\
    \n2.Or send me any coordinates in format\n44.12, 132.11\
    \n(From new line with any precicion in range -90...90, -180...180)\
    \nOr may be you are feeling /lucky today?\
    \nAlso, you can write /help if you still have questions"
    return msg


# just returns help msg
def get_help_msg(full_name):
    msg = f"Eager to help, {full_name}!\
    \nHere are some examples of proper interaction with me:\
    \n1.You can send me an adress (please, write city name explicitly)\
    \nRed square, Moscow\
    \nМосква, Театральная площадь, 1\
    \n2.Or send me any coordinates in format\n44.12, 132.11\
    \n(From new line with any precicion in range -90...90, -180...180)\
    \n55.759382, 37.618999\
    \n40.712380, -74.012782"
    return msg