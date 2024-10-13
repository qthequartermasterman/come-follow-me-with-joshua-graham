"""Generate an episode of "Come, Follow Me with Joshua Graham"."""

import datetime
import functools
import hashlib
import itertools
import logging
import multiprocessing
import os
import pathlib
import re
import shutil
import warnings
from typing import Any

import bs4
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import httpx
import magentic
import moviepy.editor as mpy
import pydantic
import pydub
import tqdm
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from googleapiclient.http import MediaFileUpload
from typing_extensions import Callable, ParamSpec, Self, TypeVar

logging.basicConfig(level=logging.INFO)

P = ParamSpec("P")
Model = TypeVar("Model", bound=pydantic.BaseModel)

# OAuth 2.0 credentials file, obtained from Google Developer Console
CLIENT_SECRETS_FILE = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

# API scopes
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# API service name and version
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

YOUTUBE_TAGS = [
    "comefollowme",
    "bookofmormon",
    "newtestament",
    "oldtestament",
    "bible",
    "Christian",
    "jesuschrist",
    "JoshuaGraham",
    "BookOfMormon",
    "FalloutNewVegas",
    "ScriptureStudy",
    "ComeFollowMe",
    "3Nephi",
    "FaithAndPerseverance",
    "SpiritualGuidance",
    "GospelInsights",
    "LDSFaith",
    "LightInDarkness",
    "TrialsAndFaith",
    "ChristianFaith",
    "BurnedMan",
    "OvercomingDoubt",
    "FaithInHardTimes",
    "SpiritualSurvival",
    "PersonalReflection",
    "SpiritualStrength",
    "ScriptureInsights",
    "JesusChrist",
    "SpiritualWarfare",
    "ReligiousReflection",
    "SpiritualEndurance",
    "PropheticSigns",
    "EndureToTheEnd",
    "ChristianLessons",
]

YOUTUBE_DESCRIPTION_DISCLAIMER = """\
Who is Joshua Graham?
Joshua Graham is a fictional character from the popular video game Fallout: New Vegas. Known as "The Burned Man," he \
is a former war chief turned repentant and deeply spiritual figure. This podcast uses the unique voice of Joshua \
Graham to offer scripture study and reflections, merging the character’s fictional narrative of redemption with \
profound spiritual insights.

Disclaimer:
The voice of Joshua Graham in this podcast is AI-generated and is used for storytelling and educational purposes. \
Joshua Graham is a fictional character from Fallout: New Vegas, and this content is not affiliated with or endorsed \
by Bethesda or Obsidian Entertainment. The views presented here do not necessarily reflect official doctrine or \
positions of the Church of Jesus Christ of Latter-day Saints.

Subscribe for more scripture studies and reflections on faith, redemption, and the teachings of Jesus Christ, all \
through the lens of Joshua Graham.
"""

# All the proper names in the Book of Mormon should be replaced with the phoneme tags
NAMES = {
    "1 Nephi ": 'first <phoneme alphabet="ipa" ph="ˈniː.faɪ">Nephi</phoneme> ',
    "2 Nephi ": 'second <phoneme alphabet="ipa" ph="ˈniː.faɪ">Nephi</phoneme> ',
    "3 Nephi ": 'third <phoneme alphabet="ipa" ph="ˈniː.faɪ">Nephi</phoneme> ',
    "4 Nephi ": 'fourth <phoneme alphabet="ipa" ph="ˈniː.faɪ">Nephi</phoneme> ',
    "1 Samuel ": "first Samuel ",
    "2 Samuel ": "second Samuel ",
    "1 Kings ": "first Kings ",
    "2 Kings ": "second Kings ",
    "1 Chronicles ": "first Chronicles ",
    "2 Chronicles ": "second Chronicles ",
    "1 Corinthians ": "first Corinthians ",
    "2 Corinthians ": "second Corinthians ",
    "1 Thessalonians ": "first Thessalonians ",
    "2 Thessalonians ": "second Thessalonians ",
    "1 Timothy ": "first Timothy ",
    "2 Timothy ": "second Timothy ",
    "1 Peter ": "first Peter ",
    "2 Peter ": "second Peter ",
    "1 John ": "first John ",
    "2 John ": "second John ",
    "3 John ": "third John ",
    "Aaron ": '<phoneme alphabet="ipa" ph="ˈɛrʹan">Aaron</phoneme> ',
    "Abel ": '<phoneme alphabet="ipa" ph="ˈeɪ.bəl">Abel</phoneme> ',
    "Abinadi ": '<phoneme alphabet="ipa" ph="əˈbɪnʹəˌdaɪ">Abinadi</phoneme> ',
    "Abinadom ": '<phoneme alphabet="ipa" ph="əˈbɪnʹəˌdʌm">Abinadom</phoneme> ',
    "Abish ": '<phoneme alphabet="ipa" ph="ˈeɪ.bɪʃ">Abish</phoneme> ',
    "Ablom ": '<phoneme alphabet="ipa" ph="ˈæbləm">Ablom</phoneme> ',
    "Abraham ": '<phoneme alphabet="ipa" ph="ˈeɪ.brəˌhæm">Abraham</phoneme> ',
    "Adam ": '<phoneme alphabet="ipa" ph="ˈædʌm">Adam</phoneme> ',
    "Agosh ": '<phoneme alphabet="ipa" ph="ˈeɪ.gɑʃ">Agosh</phoneme> ',
    "Aha ": '<phoneme alphabet="ipa" ph="ˈeɪ.hɑ">Aha</phoneme> ',
    "Ahah ": '<phoneme alphabet="ipa" ph="ˈeɪ.hɑ">Ahah</phoneme> ',
    "Ahaz ": '<phoneme alphabet="ipa" ph="ˈeɪ.hæz">Ahaz</phoneme> ',
    "Aiath ": '<phoneme alphabet="ipa" ph="ˈaɪ.æθ">Aiath</phoneme> ',
    "Akish ": '<phoneme alphabet="ipa" ph="ˈeɪ.kɪʃ">Akish</phoneme> ',
    "Alma ": '<phoneme alphabet="ipa" ph="ˈæl.mʌ">Alma</phoneme> ',
    "Alpha ": '<phoneme alphabet="ipa" ph="ˈæl.fʌ">Alpha</phoneme> ',
    "Amaleki ": '<phoneme alphabet="ipa" ph="əˈmælʹəˌkaɪ">Amaleki</phoneme> ',
    "Amalekite ": '<phoneme alphabet="ipa" ph="əˈmælʹəˌkaɪt">Amalekite</phoneme> ',
    "Amalickiah ": '<phoneme alphabet="ipa" ph="əˈmælʹəˌkaɪʌ">Amalickiah</phoneme> ',
    "Amalickiahite ": '<phoneme alphabet="ipa" ph="əˈmælʹəˌkaɪʌˌaɪt">Amalickiahite</phoneme> ',
    "Amaron ": '<phoneme alphabet="ipa" ph="əˈmeɪ.rʌn">Amaron</phoneme> ',
    "Amgid ": '<phoneme alphabet="ipa" ph="ˈæm.gɪd">Amgid</phoneme> ',
    "Aminadab ": '<phoneme alphabet="ipa" ph="əˈmɪnʹəˌdæb">Aminadab</phoneme> ',
    "Aminadi ": '<phoneme alphabet="ipa" ph="əˈmɪnʹəˌdaɪ">Aminadi</phoneme> ',
    "Amlici ": '<phoneme alphabet="ipa" ph="ˈæm.lɪ.saɪ">Amlici</phoneme> ',
    "Amlicite ": '<phoneme alphabet="ipa" ph="ˈæm.lɪ.saɪt">Amlicite</phoneme> ',
    "Ammah ": '<phoneme alphabet="ipa" ph="ˈæm.mɑ">Ammah</phoneme> ',
    "Ammaron ": '<phoneme alphabet="ipa" ph="ˈæm.əˌrɑn">Ammaron</phoneme> ',
    "Ammon ": '<phoneme alphabet="ipa" ph="ˈæm.ʌn">Ammon</phoneme> ',
    "Ammonihah ": '<phoneme alphabet="ipa" ph="ˈæm.ʌˌnaɪ.hɑ">Ammonihah</phoneme> ',
    "Ammonihahite ": '<phoneme alphabet="ipa" ph="ˈæm.ʌˌnaɪ.hɑˌaɪt">Ammonihahite</phoneme> ',
    "Ammonite ": '<phoneme alphabet="ipa" ph="ˈæm.ʌˌnaɪt">Ammonite</phoneme> ',
    "Ammoron ": '<phoneme alphabet="ipa" ph="ˈæm.ɔr.ʌn">Ammoron</phoneme> ',
    "Amnigaddah ": '<phoneme alphabet="ipa" ph="ˈæm.nɪˌgædʌ">Amnigaddah</phoneme> ',
    "Amnihu ": '<phoneme alphabet="ipa" ph="ˈæm.naɪ.hu">Amnihu</phoneme> ',
    "Amnor ": '<phoneme alphabet="ipa" ph="ˈæm.nɔr">Amnor</phoneme> ',
    "Amoron ": '<phoneme alphabet="ipa" ph="əˈmɔr.ʌn">Amoron</phoneme> ',
    "Amos ": '<phoneme alphabet="ipa" ph="ˈeɪ.mʌs">Amos</phoneme> ',
    "Amoz ": '<phoneme alphabet="ipa" ph="ˈeɪ.mʌz">Amoz</phoneme> ',
    "Amulek ": '<phoneme alphabet="ipa" ph="ˈæm.juˌlɛk">Amulek</phoneme> ',
    "Amulon ": '<phoneme alphabet="ipa" ph="ˈæm.juˌlɑn">Amulon</phoneme> ',
    "Amulonites ": '<phoneme alphabet="ipa" ph="ˈæm.juˌlɑnˌaɪts">Amulonites</phoneme> ',
    "Anathoth ": '<phoneme alphabet="ipa" ph="ˈæn.əˌtɑθ">Anathoth</phoneme> ',
    "Angola ": '<phoneme alphabet="ipa" ph="ænˈgoʊ.lʌ">Angola</phoneme> ',
    "Ani-Anti ": (
        '<phoneme alphabet="ipa" ph="ˈæn.aɪ">Ani</phoneme> <phoneme alphabet="ipa" ph="ˈæn.ti">Anti</phoneme> '
    ),
    "Anti-Nephi-Lehi ": (
        '<phoneme alphabet="ipa" ph="ˈæn.ti">Anti</phoneme> <phoneme alphabet="ipa" ph="ˈniː.faɪ">Nephi</phoneme>'
        ' <phoneme alphabet="ipa" ph="ˈliː.haɪ">Lehi</phoneme> '
    ),
    "Anti-Nephi-Lehies ": (
        '<phoneme alphabet="ipa" ph="ˈæn.ti">Anti</phoneme> <phoneme alphabet="ipa" ph="ˈniː.faɪ">Nephi</phoneme>'
        ' <phoneme alphabet="ipa" ph="ˈliː.haɪz">Lehies</phoneme> '
    ),
    "Antiomno ": '<phoneme alphabet="ipa" ph="ˈæn.tiˈɑm.noʊ">Antiomno</phoneme> ',
    "Antion ": '<phoneme alphabet="ipa" ph="ˈæn.tiˈɑn">Antion</phoneme> ',
    "Antionah ": '<phoneme alphabet="ipa" ph="ˈæn.tiˈɑn.ə">Antionah</phoneme> ',
    "Antionum ": '<phoneme alphabet="ipa" ph="ˈæn.tiˈoʊ.nʌm">Antionum</phoneme> ',
    "Antiparah ": '<phoneme alphabet="ipa" ph="ˈæn.tiˈpɑr.ə">Antiparah</phoneme> ',
    "Antipas ": '<phoneme alphabet="ipa" ph="ˈæn.tiˈpæs">Antipas</phoneme> ',
    "Antipus ": '<phoneme alphabet="ipa" ph="ˈæn.tiˈpʌs">Antipus</phoneme> ',
    "Antum ": '<phoneme alphabet="ipa" ph="ˈæn.tʌm">Antum</phoneme> ',
    "Archeantus ": '<phoneme alphabet="ipa" ph="ˈɑr.kiˈæn.tʌs">Archeantus</phoneme> ',
    "Arpad ": '<phoneme alphabet="ipa" ph="ˈɑr.pæd">Arpad</phoneme> ',
    "Assyria ": '<phoneme alphabet="ipa" ph="əˈsɪr.i.ə">Assyria</phoneme> ',
    "Babylon ": '<phoneme alphabet="ipa" ph="ˈbæb.ɪ.lʌn">Babylon</phoneme> ',
    "Bashan ": '<phoneme alphabet="ipa" ph="ˈbeɪ.ʃæn">Bashan</phoneme> ',
    "Benjamin ": '<phoneme alphabet="ipa" ph="bɛnˈdʒæ.mɪn">Benjamin</phoneme> ',
    "Bethabara ": '<phoneme alphabet="ipa" ph="bɛθˈæb.ə.rʌ">Bethabara</phoneme> ',
    "Boaz ": '<phoneme alphabet="ipa" ph="boʊˈæz">Boaz</phoneme> ',
    "Bountiful ": '<phoneme alphabet="ipa" ph="ˈbaʊn.tɪ.fʊl">Bountiful</phoneme> ',
    "Cain ": '<phoneme alphabet="ipa" ph="keɪn">Cain</phoneme> ',
    "Calno ": '<phoneme alphabet="ipa" ph="ˈkæl.noʊ">Calno</phoneme> ',
    "Carchemish ": '<phoneme alphabet="ipa" ph="ˈkɑr.kɛ.mɪʃ">Carchemish</phoneme> ',
    "Cezoram ": '<phoneme alphabet="ipa" ph="ˈsiː.zɔr.ʌm">Cezoram</phoneme> ',
    "Chaldeans ": '<phoneme alphabet="ipa" ph="ˈkæl.di.ənz">Chaldeans</phoneme> ',
    "Chaldees ": '<phoneme alphabet="ipa" ph="ˈkæl.diz">Chaldees</phoneme> ',
    "Chemish ": '<phoneme alphabet="ipa" ph="ˈkɛ.mɪʃ">Chemish</phoneme> ',
    "Cherubim ": '<phoneme alphabet="ipa" ph="ˈtʃɛr.ə.bɪm">Cherubim</phoneme> ',
    "Cohor ": '<phoneme alphabet="ipa" ph="ˈkoʊ.hɔr">Cohor</phoneme> ',
    "Com ": '<phoneme alphabet="ipa" ph="koʊm">Com</phoneme> ',
    "Comnor ": '<phoneme alphabet="ipa" ph="ˈkoʊm.nɔr">Comnor</phoneme> ',
    "Corianton ": '<phoneme alphabet="ipa" ph="koʊr.iˈæn.tʌn">Corianton</phoneme> ',
    "Coriantor ": '<phoneme alphabet="ipa" ph="koʊr.iˈæn.tɔr">Coriantor</phoneme> ',
    "Coriantum ": '<phoneme alphabet="ipa" ph="koʊr.iˈæn.tʌm">Coriantum</phoneme> ',
    "Coriantumr ": '<phoneme alphabet="ipa" ph="koʊr.iˈæn.tʌ.mɛr">Coriantumr</phoneme> ',
    "Corihor ": '<phoneme alphabet="ipa" ph="ˈkoʊr.ɪ.hɔr">Corihor</phoneme> ',
    "Corom ": '<phoneme alphabet="ipa" ph="ˈkoʊr.ʌm">Corom</phoneme> ',
    "Cumeni ": '<phoneme alphabet="ipa" ph="kuˈmeɪ.naɪ">Cumeni</phoneme> ',
    "Cumenihah ": '<phoneme alphabet="ipa" ph="kuˈmeɪ.naɪ.hɑ">Cumenihah</phoneme> ',
    "Cumom ": '<phoneme alphabet="ipa" ph="ˈkuː.mʌm">Cumom</phoneme> ',
    "Cumorah ": '<phoneme alphabet="ipa" ph="ˈkuː.mɔr.ʌ">Cumorah</phoneme> ',
    "Curelom ": '<phoneme alphabet="ipa" ph="ˈkʊr.ɛ.lʌm">Curelom</phoneme> ',
    "Deseret ": '<phoneme alphabet="ipa" ph="ˌdɛz.əˈrɛt">Deseret</phoneme> ',
    "Desolation ": '<phoneme alphabet="ipa" ph="ˌdɛs.əˈleɪ.ʃən">Desolation</phoneme> ',
    "Edom ": '<phoneme alphabet="ipa" ph="ˈiː.dʌm">Edom</phoneme> ',
    "Egypt ": '<phoneme alphabet="ipa" ph="ˈiː.dʒɪpt">Egypt</phoneme> ',
    "Egyptian ": '<phoneme alphabet="ipa" ph="iˈdʒɪp.ʃən">Egyptian</phoneme> ',
    "Elam ": '<phoneme alphabet="ipa" ph="ˈiː.lʌm">Elam</phoneme> ',
    "Elijah ": '<phoneme alphabet="ipa" ph="ɪˈlaɪ.dʒə">Elijah</phoneme> ',
    "Emer ": '<phoneme alphabet="ipa" ph="ˈiː.mɜr">Emer</phoneme> ',
    "Emron ": '<phoneme alphabet="ipa" ph="ˈɛm.rɑn">Emron</phoneme> ',
    "Enos ": '<phoneme alphabet="ipa" ph="ˈiː.nʌs">Enos</phoneme> ',
    "Ephah ": '<phoneme alphabet="ipa" ph="ˈiː.fɑ">Ephah</phoneme> ',
    "Ephraim ": '<phoneme alphabet="ipa" ph="ˈiː.frɪm">Ephraim</phoneme> ',
    "Esrom ": '<phoneme alphabet="ipa" ph="ˈɛz.rʌm">Esrom</phoneme> ',
    "Ethem ": '<phoneme alphabet="ipa" ph="ˈiː.θʌm">Ethem</phoneme> ',
    "Ether ": '<phoneme alphabet="ipa" ph="ˈiː.θʌr">Ether</phoneme> ',
    "Eve ": '<phoneme alphabet="ipa" ph="iːv">Eve</phoneme> ',
    "Ezias ": '<phoneme alphabet="ipa" ph="ˈɛz.aɪ.əs">Ezias</phoneme> ',
    "Ezrom ": '<phoneme alphabet="ipa" ph="ˈɛz.rʌm">Ezrom</phoneme> ',
    "Gad ": '<phoneme alphabet="ipa" ph="gæd">Gad</phoneme> ',
    "Gadiandi ": '<phoneme alphabet="ipa" ph="ˌgæd.iˈæn.daɪ">Gadiandi</phoneme> ',
    "Gadianton ": '<phoneme alphabet="ipa" ph="ˌgæd.iˈæn.tʌn">Gadianton</phoneme> ',
    "Gadiomnah ": '<phoneme alphabet="ipa" ph="ˌgæd.iˈɑm.nʌ">Gadiomnah</phoneme> ',
    "Gallim ": '<phoneme alphabet="ipa" ph="ˈgæl.ɪm">Gallim</phoneme> ',
    "Gazelem ": '<phoneme alphabet="ipa" ph="ˈgeɪ.zɛ.lɪm">Gazelem</phoneme> ',
    "Geba ": '<phoneme alphabet="ipa" ph="ˈgiː.bʌ">Geba</phoneme> ',
    "Gebim ": '<phoneme alphabet="ipa" ph="ˈgiː.bɪm">Gebim</phoneme> ',
    "Gibeah ": '<phoneme alphabet="ipa" ph="ˈgɪ.bi.ə">Gibeah</phoneme> ',
    "Gid ": '<phoneme alphabet="ipa" ph="gɪd">Gid</phoneme> ',
    "Giddianhi ": '<phoneme alphabet="ipa" ph="gɪd.iˈæn.haɪ">Giddianhi</phoneme> ',
    "Giddonah ": '<phoneme alphabet="ipa" ph="gɪˈdɔ.nʌ">Giddonah</phoneme> ',
    "Gideon ": '<phoneme alphabet="ipa" ph="ˈgɪd.i.ən">Gideon</phoneme> ',
    "Gidgiddonah ": '<phoneme alphabet="ipa" ph="gɪdˈgɪd.oʊ.nʌ">Gidgiddonah</phoneme> ',
    "Gidgiddoni ": '<phoneme alphabet="ipa" ph="gɪdˈgɪd.oʊ.naɪ">Gidgiddoni</phoneme> ',
    "Gilead ": '<phoneme alphabet="ipa" ph="ˈgɪ.li.əd">Gilead</phoneme> ',
    "Gilgah ": '<phoneme alphabet="ipa" ph="ˈgɪl.gɑ">Gilgah</phoneme> ',
    "Gilgal ": '<phoneme alphabet="ipa" ph="ˈgɪl.gɑl">Gilgal</phoneme> ',
    "Gimgimno ": '<phoneme alphabet="ipa" ph="ˈgɪmˈgɪm.noʊ">Gimgimno</phoneme> ',
    "Gomorrah ": '<phoneme alphabet="ipa" ph="gəˈmɔr.ʌ">Gomorrah</phoneme> ',
    "Hagoth ": '<phoneme alphabet="ipa" ph="ˈheɪ.gɑθ">Hagoth</phoneme> ',
    "Hamath ": '<phoneme alphabet="ipa" ph="ˈheɪ.mæθ">Hamath</phoneme> ',
    "Hearthom ": '<phoneme alphabet="ipa" ph="ˈhɜr.θʌm">Hearthom</phoneme> ',
    "Helam ": '<phoneme alphabet="ipa" ph="ˈhiː.lʌm">Helam</phoneme> ',
    "Helaman ": '<phoneme alphabet="ipa" ph="ˈhiː.lʌ.mʌn">Helaman</phoneme> ',
    "Helem ": '<phoneme alphabet="ipa" ph="ˈhiː.lɛm">Helem</phoneme> ',
    "Helorum ": '<phoneme alphabet="ipa" ph="ˈhiː.lɔr.ʌm">Helorum</phoneme> ',
    "Hem ": '<phoneme alphabet="ipa" ph="hɛm">Hem</phoneme> ',
    "Hermounts ": '<phoneme alphabet="ipa" ph="ˈhɜr.maʊnts">Hermounts</phoneme> ',
    "Heshlon ": '<phoneme alphabet="ipa" ph="ˈhɛʃ.lɑn">Heshlon</phoneme> ',
    "Heth ": '<phoneme alphabet="ipa" ph="hɛθ">Heth</phoneme> ',
    "Himni ": '<phoneme alphabet="ipa" ph="ˈhɪm.naɪ">Himni</phoneme> ',
    "Horeb ": '<phoneme alphabet="ipa" ph="ˈhɔr.ɛb">Horeb</phoneme> ',
    "Immanuel ": '<phoneme alphabet="ipa" ph="ɪˈmæn.juˌɛl">Immanuel</phoneme> ',
    "Irreantum ": '<phoneme alphabet="ipa" ph="ɪˈriː.æn.tʌm">Irreantum</phoneme> ',
    "Isaac ": '<phoneme alphabet="ipa" ph="ˈaɪ.zæk">Isaac</phoneme> ',
    "Isabel ": '<phoneme alphabet="ipa" ph="ˈɪz.əˌbɛl">Isabel</phoneme> ',
    "Isaiah ": '<phoneme alphabet="ipa" ph="aɪˈzeɪ.ə">Isaiah</phoneme> ',
    "Ishmael ": '<phoneme alphabet="ipa" ph="ˈɪʃ.meɪ.əl">Ishmael</phoneme> ',
    "Ishmaelite ": '<phoneme alphabet="ipa" ph="ˈɪʃ.meɪ.ə.laɪt">Ishmaelite</phoneme> ',
    "Israel ": '<phoneme alphabet="ipa" ph="ˈɪz.reɪl">Israel</phoneme> ',
    "Israelite ": '<phoneme alphabet="ipa" ph="ˈɪz.reɪ.laɪt">Israelite</phoneme> ',
    "Jacob ": '<phoneme alphabet="ipa" ph="ˈdʒeɪ.kʌb">Jacob</phoneme> ',
    "Jacobite ": '<phoneme alphabet="ipa" ph="ˈdʒeɪ.kʌ.baɪt">Jacobite</phoneme> ',
    "Jacobugath ": '<phoneme alphabet="ipa" ph="ˈdʒeɪ.kʌˌbju.gæθ">Jacobugath</phoneme> ',
    "Jacom ": '<phoneme alphabet="ipa" ph="ˈdʒeɪ.kʌm">Jacom</phoneme> ',
    "Jared ": '<phoneme alphabet="ipa" ph="ˈdʒɛr.əd">Jared</phoneme> ',
    "Jaredite ": '<phoneme alphabet="ipa" ph="ˈdʒɛr.əˌdaɪt">Jaredite</phoneme> ',
    "Jarom ": '<phoneme alphabet="ipa" ph="ˈdʒɛr.ʌm">Jarom</phoneme> ',
    "Jashon ": '<phoneme alphabet="ipa" ph="ˈdʒæ.ʃʌn">Jashon</phoneme> ',
    "Jeberechiah ": '<phoneme alphabet="ipa" ph="ˌdʒɛb.ə.rəˈkaɪ.ə">Jeberechiah</phoneme> ',
    "Jehovah ": '<phoneme alphabet="ipa" ph="dʒɪˈhoʊ.və">Jehovah</phoneme> ',
    "Jeneum ": '<phoneme alphabet="ipa" ph="dʒəˈniː.ʌm">Jeneum</phoneme> ',
    "Jeremiah ": '<phoneme alphabet="ipa" ph="ˌdʒɛr.əˈmaɪ.ə">Jeremiah</phoneme> ',
    "Jershon ": '<phoneme alphabet="ipa" ph="ˈdʒɜr.ʃɑn">Jershon</phoneme> ',
    "Joshua ": '<phoneme alphabet="ipa" ph="ˈdʒɒʃ.ju.ə">Joshua</phoneme> ',
    "Jotham ": '<phoneme alphabet="ipa" ph="ˈdʒoʊ.θəm">Jotham</phoneme> ',
    "Judah ": '<phoneme alphabet="ipa" ph="ˈdʒuː.də">Judah</phoneme> ',
    "Judea ": '<phoneme alphabet="ipa" ph="dʒuːˈdiː.ə">Judea</phoneme> ',
    "Kib ": '<phoneme alphabet="ipa" ph="kɪb">Kib</phoneme> ',
    "Kim ": '<phoneme alphabet="ipa" ph="kɪm">Kim</phoneme> ',
    "Kimnor ": '<phoneme alphabet="ipa" ph="ˈkɪm.nɔr">Kimnor</phoneme> ',
    "Kish ": '<phoneme alphabet="ipa" ph="kɪʃ">Kish</phoneme> ',
    "Kishkumen ": '<phoneme alphabet="ipa" ph="kɪʃˈkuː.mən">Kishkumen</phoneme> ',
    "Korihor ": '<phoneme alphabet="ipa" ph="ˈkɔr.ɪ.hɔr">Korihor</phoneme> ',
    "Kumen ": '<phoneme alphabet="ipa" ph="ˈkuː.mən">Kumen</phoneme> ',
    "Kumenonhi ": '<phoneme alphabet="ipa" ph="ˈkuː.məˌnɑn.haɪ">Kumenonhi</phoneme> ',
    "Laban ": '<phoneme alphabet="ipa" ph="ˈleɪ.bən">Laban</phoneme> ',
    "Lachoneus ": '<phoneme alphabet="ipa" ph="læˈkoʊ.ni.əs">Lachoneus</phoneme> ',
    "Laish ": '<phoneme alphabet="ipa" ph="leɪ.ɪʃ">Laish</phoneme> ',
    "Lamah ": '<phoneme alphabet="ipa" ph="ˈleɪ.mɑ">Lamah</phoneme> ',
    "Laman ": '<phoneme alphabet="ipa" ph="ˈleɪ.mən">Laman</phoneme> ',
    "Lamanite ": '<phoneme alphabet="ipa" ph="ˈleɪ.məˌnaɪt">Lamanite</phoneme> ',
    "Lamoni ": '<phoneme alphabet="ipa" ph="ləˈmoʊ.ni">Lamoni</phoneme> ',
    "Lebanon ": '<phoneme alphabet="ipa" ph="ˈlɛ.bə.nʌn">Lebanon</phoneme> ',
    "Lehi ": '<phoneme alphabet="ipa" ph="ˈliː.haɪ">Lehi</phoneme> ',
    "Lehi-Nephi ": '<phoneme alphabet="ipa" ph="ˈliː.haɪˈniː.faɪ">Lehi-Nephi</phoneme> ',
    "Lehonti ": '<phoneme alphabet="ipa" ph="lɪˈhɑn.ti">Lehonti</phoneme> ',
    "Lemuel ": '<phoneme alphabet="ipa" ph="ˈlɛm.ju.əl">Lemuel</phoneme> ',
    "Lemuelite ": '<phoneme alphabet="ipa" ph="ˈlɛm.ju.əˌlaɪt">Lemuelite</phoneme> ',
    "Levi ": '<phoneme alphabet="ipa" ph="ˈliː.vaɪ">Levi</phoneme> ',
    "Liahona ": '<phoneme alphabet="ipa" ph="ˈliːəˌhoʊ.nə">Liahona</phoneme> ',
    "Lib ": '<phoneme alphabet="ipa" ph="lɪb">Lib</phoneme> ',
    "Limhah ": '<phoneme alphabet="ipa" ph="ˈlɪm.hɑ">Limhah</phoneme> ',
    "Limher ": '<phoneme alphabet="ipa" ph="ˈlɪm.hɜr">Limher</phoneme> ',
    "Limhi ": '<phoneme alphabet="ipa" ph="ˈlɪm.haɪ">Limhi</phoneme> ',
    "Limnah ": '<phoneme alphabet="ipa" ph="ˈlɪm.nɑ">Limnah</phoneme> ',
    "Luram ": '<phoneme alphabet="ipa" ph="ˈlʊr.ʌm">Luram</phoneme> ',
    "Madmenah ": '<phoneme alphabet="ipa" ph="ˌmæd.məˈnɑ">Madmenah</phoneme> ',
    "Mahah ": '<phoneme alphabet="ipa" ph="ˈmeɪ.hɑ">Mahah</phoneme> ',
    "Maher-shalal-hash-baz ": '<phoneme alphabet="ipa" ph="ˈmeɪ.hɜrˌʃæ.lælˌhæʃ.bæz">Maher-shalal-hash-baz</phoneme> ',
    "Malachi ": '<phoneme alphabet="ipa" ph="ˈmæl.əˌkaɪ">Malachi</phoneme> ',
    "Manasseh ": '<phoneme alphabet="ipa" ph="məˈnæs.ə">Manasseh</phoneme> ',
    "Manti ": '<phoneme alphabet="ipa" ph="ˈmæn.taɪ">Manti</phoneme> ',
    "Mary ": '<phoneme alphabet="ipa" ph="ˈmɛr.i">Mary</phoneme> ',
    "Mathoni ": '<phoneme alphabet="ipa" ph="məˈθoʊ.ni">Mathoni</phoneme> ',
    "Mathonihah ": '<phoneme alphabet="ipa" ph="ˌmæθ.oʊˈnaɪ.hɑ">Mathonihah</phoneme> ',
    "Medes ": '<phoneme alphabet="ipa" ph="miːdz">Medes</phoneme> ',
    "Melchizedek ": '<phoneme alphabet="ipa" ph="mɛlˈkɪz.əˌdɛk">Melchizedek</phoneme> ',
    "Melek ": '<phoneme alphabet="ipa" ph="ˈmiː.lɛk">Melek</phoneme> ',
    "Michmash ": '<phoneme alphabet="ipa" ph="ˈmɪk.mæʃ">Michmash</phoneme> ',
    "Middoni ": '<phoneme alphabet="ipa" ph="mɪˈdoʊ.naɪ">Middoni</phoneme> ',
    "Midian ": '<phoneme alphabet="ipa" ph="ˈmɪd.i.ən">Midian</phoneme> ',
    "Migron ": '<phoneme alphabet="ipa" ph="ˈmaɪ.grɑn">Migron</phoneme> ',
    "Minon ": '<phoneme alphabet="ipa" ph="ˈmaɪ.nɑn">Minon</phoneme> ',
    "Moab ": '<phoneme alphabet="ipa" ph="ˈmoʊ.æb">Moab</phoneme> ',
    "Mocum ": '<phoneme alphabet="ipa" ph="ˈmoʊ.kʌm">Mocum</phoneme> ',
    "Moriancumer ": '<phoneme alphabet="ipa" ph="moʊˌriː.ænˈkuː.mɜr">Moriancumer</phoneme> ',
    "Morianton ": '<phoneme alphabet="ipa" ph="moʊˌriː.ænˈtʌn">Morianton</phoneme> ',
    "Moriantum ": '<phoneme alphabet="ipa" ph="moʊˌriː.ænˈtʌm">Moriantum</phoneme> ',
    "Mormon ": '<phoneme alphabet="ipa" ph="ˈmɔr.mʌn">Mormon</phoneme> ',
    "Moron ": '<phoneme alphabet="ipa" ph="ˈmɔr.ʌn">Moron</phoneme> ',
    "Moroni ": '<phoneme alphabet="ipa" ph="moʊˈroʊ.naɪ">Moroni</phoneme> ',
    "Moronihah ": '<phoneme alphabet="ipa" ph="moʊˌroʊ.niˈhɑ">Moronihah</phoneme> ',
    "Moses ": '<phoneme alphabet="ipa" ph="ˈmoʊ.zəs">Moses</phoneme> ',
    "Mosiah ": '<phoneme alphabet="ipa" ph="moʊˈzaɪ.ə">Mosiah</phoneme> ',
    "Mulek ": '<phoneme alphabet="ipa" ph="ˈmjuː.lɛk">Mulek</phoneme> ',
    "Muloki ": '<phoneme alphabet="ipa" ph="ˈmjuː.ləˌkaɪ">Muloki</phoneme> ',
    "Nahom ": '<phoneme alphabet="ipa" ph="ˈneɪ.hʌm">Nahom</phoneme> ',
    "Naphtali ": '<phoneme alphabet="ipa" ph="ˈnæf.tə.laɪ">Naphtali</phoneme> ',
    "Nazareth ": '<phoneme alphabet="ipa" ph="ˈnæz.ə.rɛθ">Nazareth</phoneme> ',
    "Neas ": '<phoneme alphabet="ipa" ph="ˈniː.æs">Neas</phoneme> ',
    "Nehor ": '<phoneme alphabet="ipa" ph="ˈniː.hɔr">Nehor</phoneme> ',
    "Nephi ": '<phoneme alphabet="ipa" ph="ˈniː.faɪ">Nephi</phoneme> ',
    "Nephihah ": '<phoneme alphabet="ipa" ph="niːˈfaɪ.hɑ">Nephihah</phoneme> ',
    "Nephite ": '<phoneme alphabet="ipa" ph="ˈniː.faɪt">Nephite</phoneme> ',
    "Neum ": '<phoneme alphabet="ipa" ph="ˈniː.ʌm">Neum</phoneme> ',
    "Nimrah ": '<phoneme alphabet="ipa" ph="ˈnɪm.rɑ">Nimrah</phoneme> ',
    "Nimrod ": '<phoneme alphabet="ipa" ph="ˈnɪm.rɑd">Nimrod</phoneme> ',
    "Noah ": '<phoneme alphabet="ipa" ph="ˈnoʊ.ə">Noah</phoneme> ',
    "Ogath ": '<phoneme alphabet="ipa" ph="ˈoʊ.gæθ">Ogath</phoneme> ',
    "Omega ": '<phoneme alphabet="ipa" ph="oʊˈmeɪ.gə">Omega</phoneme> ',
    "Omer ": '<phoneme alphabet="ipa" ph="ˈoʊ.mɜr">Omer</phoneme> ',
    "Omner ": '<phoneme alphabet="ipa" ph="ˈɑm.nɜr">Omner</phoneme> ',
    "Omni ": '<phoneme alphabet="ipa" ph="ˈɑm.naɪ">Omni</phoneme> ',
    "Onidah ": '<phoneme alphabet="ipa" ph="oʊˈnaɪ.dɑ">Onidah</phoneme> ',
    "Onihah ": '<phoneme alphabet="ipa" ph="oʊˈnaɪ.hɑ">Onihah</phoneme> ',
    "Onti ": '<phoneme alphabet="ipa" ph="ˈɑn.taɪ">Onti</phoneme> ',
    "Ophir ": '<phoneme alphabet="ipa" ph="ˈoʊ.fɪr">Ophir</phoneme> ',
    "Oreb ": '<phoneme alphabet="ipa" ph="ˈɔr.ɛb">Oreb</phoneme> ',
    "Orihah ": '<phoneme alphabet="ipa" ph="oʊˈraɪ.hɑ">Orihah</phoneme> ',
    "Paanchi ": '<phoneme alphabet="ipa" ph="pæˈæn.kaɪ">Paanchi</phoneme> ',
    "Pachus ": '<phoneme alphabet="ipa" ph="ˈpæ.kəs">Pachus</phoneme> ',
    "Pacumeni ": '<phoneme alphabet="ipa" ph="pæˌkjʊˈmɛ.naɪ">Pacumeni</phoneme> ',
    "Pagag ": '<phoneme alphabet="ipa" ph="ˈpeɪ.gæg">Pagag</phoneme> ',
    "Pahoran ": '<phoneme alphabet="ipa" ph="pɑˈhoʊ.rʌn">Pahoran</phoneme> ',
    "Palestina ": '<phoneme alphabet="ipa" ph="ˌpæl.əˈstiː.nə">Palestina</phoneme> ',
    "Pathros ": '<phoneme alphabet="ipa" ph="ˈpæθ.roʊs">Pathros</phoneme> ',
    "Pekah ": '<phoneme alphabet="ipa" ph="ˈpiː.kɑ">Pekah</phoneme> ',
    "Pharaoh ": '<phoneme alphabet="ipa" ph="ˈfɛr.oʊ">Pharaoh</phoneme> ',
    "Philistine ": '<phoneme alphabet="ipa" ph="ˈfɪl.ɪˌstiːn">Philistine</phoneme> ',
    "Rabbanah ": '<phoneme alphabet="ipa" ph="rəˈbæn.ə">Rabbanah</phoneme> ',
    "Rahab ": '<phoneme alphabet="ipa" ph="ˈreɪ.hæb">Rahab</phoneme> ',
    "Ramah ": '<phoneme alphabet="ipa" ph="ˈrɑ.mɑ">Ramah</phoneme> ',
    "Ramath ": '<phoneme alphabet="ipa" ph="ˈreɪ.mæθ">Ramath</phoneme> ',
    "Rameumptom ": '<phoneme alphabet="ipa" ph="ˈræm.iˈʌmp.tʌm">Rameumptom</phoneme> ',
    "Remaliah ": '<phoneme alphabet="ipa" ph="ˌrɛ.məˈlaɪ.ə">Remaliah</phoneme> ',
    "Rezin ": '<phoneme alphabet="ipa" ph="ˈrɛz.ɪn">Rezin</phoneme> ',
    "Riplah ": '<phoneme alphabet="ipa" ph="ˈrɪp.lɑ">Riplah</phoneme> ',
    "Riplakish ": '<phoneme alphabet="ipa" ph="rɪpˈleɪ.kɪʃ">Riplakish</phoneme> ',
    "Ripliancum ": '<phoneme alphabet="ipa" ph="rɪpˌliːˈæn.kʌm">Ripliancum</phoneme> ',
    "Salem ": '<phoneme alphabet="ipa" ph="ˈseɪ.ləm">Salem</phoneme> ',
    "Sam ": '<phoneme alphabet="ipa" ph="sæm">Sam</phoneme> ',
    "Samaria ": '<phoneme alphabet="ipa" ph="səˈmɛr.i.ə">Samaria</phoneme> ',
    "Samuel ": '<phoneme alphabet="ipa" ph="ˈsæm.ju.əl">Samuel</phoneme> ',
    "Sarah ": '<phoneme alphabet="ipa" ph="ˈsɛr.ə">Sarah</phoneme> ',
    "Sariah ": '<phoneme alphabet="ipa" ph="səˈraɪ.ə">Sariah</phoneme> ',
    "Saul ": '<phoneme alphabet="ipa" ph="sɔl">Saul</phoneme> ',
    "Seantum ": '<phoneme alphabet="ipa" ph="siˈæn.tʌm">Seantum</phoneme> ',
    "Sebus ": '<phoneme alphabet="ipa" ph="ˈsiː.bʌs">Sebus</phoneme> ',
    "Seezoram ": '<phoneme alphabet="ipa" ph="ˈsiː.zɔ.rʌm">Seezoram</phoneme> ',
    "Senine ": '<phoneme alphabet="ipa" ph="ˈsɛn.aɪn">Senine</phoneme> ',
    "Senum ": '<phoneme alphabet="ipa" ph="ˈsɛ.nʌm">Senum</phoneme> ',
    "Seraphim ": '<phoneme alphabet="ipa" ph="ˈsɛr.ə.fɪm">Seraphim</phoneme> ',
    "Seth ": '<phoneme alphabet="ipa" ph="sɛθ">Seth</phoneme> ',
    "Shared ": '<phoneme alphabet="ipa" ph="ˈʃeɪ.rəd">Shared</phoneme> ',
    "Shazer ": '<phoneme alphabet="ipa" ph="ˈʃeɪ.zɜr">Shazer</phoneme> ',
    "Shearjashub ": '<phoneme alphabet="ipa" ph="ˌʃɪr.dʒæ.ʃʌb">Shearjashub</phoneme> ',
    "Shelem ": '<phoneme alphabet="ipa" ph="ˈʃeɪ.ləm">Shelem</phoneme> ',
    "Shem ": '<phoneme alphabet="ipa" ph="ʃɛm">Shem</phoneme> ',
    "Shemlon ": '<phoneme alphabet="ipa" ph="ˈʃɛm.lɑn">Shemlon</phoneme> ',
    "Shemnon ": '<phoneme alphabet="ipa" ph="ˈʃɛm.nɑn">Shemnon</phoneme> ',
    "Sherem ": '<phoneme alphabet="ipa" ph="ˈʃɛr.əm">Sherem</phoneme> ',
    "Sherrizah ": '<phoneme alphabet="ipa" ph="ˈʃɛr.aɪ.zɑ">Sherrizah</phoneme> ',
    "Sheum ": '<phoneme alphabet="ipa" ph="ˈʃiː.ʌm">Sheum</phoneme> ',
    "Shez ": '<phoneme alphabet="ipa" ph="ʃɛz">Shez</phoneme> ',
    "Shiblom ": '<phoneme alphabet="ipa" ph="ˈʃɪb.lʌm">Shiblom</phoneme> ',
    "Shiblon ": '<phoneme alphabet="ipa" ph="ˈʃɪb.lʌn">Shiblon</phoneme> ',
    "Shiblum ": '<phoneme alphabet="ipa" ph="ˈʃɪb.lʌm">Shiblum</phoneme> ',
    "Shiloah ": '<phoneme alphabet="ipa" ph="ʃaɪˈloʊ.ə">Shiloah</phoneme> ',
    "Shilom ": '<phoneme alphabet="ipa" ph="ˈʃaɪ.lʌm">Shilom</phoneme> ',
    "Shim ": '<phoneme alphabet="ipa" ph="ʃɪm">Shim</phoneme> ',
    "Shimnilom ": '<phoneme alphabet="ipa" ph="ˈʃɪm.nɪ.lɑm">Shimnilom</phoneme> ',
    "Shinar ": '<phoneme alphabet="ipa" ph="ˈʃaɪ.nɑr">Shinar</phoneme> ',
    "Shiz ": '<phoneme alphabet="ipa" ph="ʃɪz">Shiz</phoneme> ',
    "Shule ": '<phoneme alphabet="ipa" ph="ʃuːl">Shule</phoneme> ',
    "Shum ": '<phoneme alphabet="ipa" ph="ʃʌm">Shum</phoneme> ',
    "Shurr ": '<phoneme alphabet="ipa" ph="ʃɜr">Shurr</phoneme> ',
    "Sidom ": '<phoneme alphabet="ipa" ph="ˈsaɪ.dʌm">Sidom</phoneme> ',
    "Sidon ": '<phoneme alphabet="ipa" ph="ˈsaɪ.dʌn">Sidon</phoneme> ',
    "Sinai ": '<phoneme alphabet="ipa" ph="ˈsaɪ.naɪ">Sinai</phoneme> ',
    "Sinim ": '<phoneme alphabet="ipa" ph="ˈsaɪ.nɪm">Sinim</phoneme> ',
    "Siron ": '<phoneme alphabet="ipa" ph="ˈsaɪ.rʌn">Siron</phoneme> ',
    "Syria ": '<phoneme alphabet="ipa" ph="ˈsɪr.i.ə">Syria</phoneme> ',
    "Tarshish ": '<phoneme alphabet="ipa" ph="ˈtɑr.ʃɪʃ">Tarshish</phoneme> ',
    "Teancum ": '<phoneme alphabet="ipa" ph="tiˈæn.kʌm">Teancum</phoneme> ',
    "Teomner ": '<phoneme alphabet="ipa" ph="tiˈɑm.nɜr">Teomner</phoneme> ',
    "Thummim ": '<phoneme alphabet="ipa" ph="ˈθʌm.ɪm">Thummim</phoneme> ',
    "Timothy ": '<phoneme alphabet="ipa" ph="ˈtɪm.ə.θi">Timothy</phoneme> ',
    "Tubaloth ": '<phoneme alphabet="ipa" ph="ˈtuː.bʌˌlɑθ">Tubaloth</phoneme> ',
    "Uriah ": '<phoneme alphabet="ipa" ph="juˈraɪ.ə">Uriah</phoneme> ',
    "Urim ": '<phoneme alphabet="ipa" ph="ˈjʊr.ɪm">Urim</phoneme> ',
    "Uzziah ": '<phoneme alphabet="ipa" ph="juˈzaɪ.ə">Uzziah</phoneme> ',
    "Zarahemla ": '<phoneme alphabet="ipa" ph="ˌzɛr.əˈhɛm.lə">Zarahemla</phoneme> ',
    "Zebulun ": '<phoneme alphabet="ipa" ph="ˈzɛb.jʊ.lʌn">Zebulun</phoneme> ',
    "Zechariah ": '<phoneme alphabet="ipa" ph="ˌzɛk.əˈraɪ.ə">Zechariah</phoneme> ',
    "Zedekiah ": '<phoneme alphabet="ipa" ph="ˌzɛd.əˈkaɪ.ə">Zedekiah</phoneme> ',
    "Zeezrom ": '<phoneme alphabet="ipa" ph="ziːˈɛz.rʌm">Zeezrom</phoneme> ',
    "Zemnarihah ": '<phoneme alphabet="ipa" ph="ˌzɛm.nəˈraɪ.hɑ">Zemnarihah</phoneme> ',
    "Zenephi ": '<phoneme alphabet="ipa" ph="ˈziː.nəˌfaɪ">Zenephi</phoneme> ',
    "Zeniff ": '<phoneme alphabet="ipa" ph="ˈziː.nɪf">Zeniff</phoneme> ',
    "Zenock ": '<phoneme alphabet="ipa" ph="ˈziː.nʌk">Zenock</phoneme> ',
    "Zenos ": '<phoneme alphabet="ipa" ph="ˈziː.nʌs">Zenos</phoneme> ',
    "Zerahemnah ": '<phoneme alphabet="ipa" ph="ˌzɛr.əˈhɛm.nɑ">Zerahemnah</phoneme> ',
    "Zeram ": '<phoneme alphabet="ipa" ph="ˈzɛr.ʌm">Zeram</phoneme> ',
    "Zerin ": '<phoneme alphabet="ipa" ph="ˈzɛr.ɪn">Zerin</phoneme> ',
    "Ziff ": '<phoneme alphabet="ipa" ph="zɪf">Ziff</phoneme> ',
    "Zion ": '<phoneme alphabet="ipa" ph="ˈzaɪ.ən">Zion</phoneme> ',
    "Zoram ": '<phoneme alphabet="ipa" ph="ˈzoʊ.rʌm">Zoram</phoneme> ',
    "Zoramite ": '<phoneme alphabet="ipa" ph="ˈzoʊ.rʌˌmaɪt">Zoramite</phoneme> ',
}
ITE_NAMES = {k.replace("ite", "ites"): v.replace("ɪt", "ɪts") for k, v in NAMES.items() if "ite" in k}

NUM_THROUGH_NUM_REGEX = re.compile(r"(\d+)[-–](\d+)")
DOCTRINE_AND_COVENANTS_SECTION_VERSE_REGEX = re.compile(
    r"(Doctrine and Covenants|Doctrine & Covenants|D&C) (\d+):(\d+)"
)
CHAPTER_VERSE_REGEX = re.compile(r"(\d+):(\d+)")

VOICE_SETTINGS = VoiceSettings(
    stability=0.34,
    similarity_boost=0.8,
    style=0.2,
)


EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT = """\
You are Joshua Graham, the Burned Man, of Fallout: New Vegas fame. You have recently been called as your ward Sunday
School teacher teaching the Book of Mormon using the Come, Follow Me curriculum. Using the attached document, please
outline a podcast episode based on this week's curriculum ({curriculum_string}). 

Each segment should be about 4-5 minutes (~800-1000 words) long, including some scriptural references from the assigned
curriculum and some other connection, at least. Make as many relevant references as possible to provide commentary on.
The content should be spiritually uplifting and doctrinally sound according to the official positions of the Church of
Jesus Christ of Latter-day Saints.

Make sure to make the outline feels like it was written by you, Joshua Graham. You may include personal anecdotes or 
insights. Recall that Joshua Graham is well trainined in languages, so feel free to make language connections. The 
content should not just be generic. Please also dive into the scriptures wherever possible, providing 
doctrinally-sound commentary.
"""
assert EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT.strip()

logging.info("Fetching Joshua Graham background text...")
JOSHUA_GRAHAM_BACKGROUND_TEXT = httpx.get("https://fallout.fandom.com/wiki/Joshua_Graham?action=raw").text
assert JOSHUA_GRAHAM_BACKGROUND_TEXT.strip()

EPISODE_FLESH_OUT_GENERATION_PROMPT = """\
This is the episode outline:

```
{episode_outline}
```

Now that we have an episode outline written by you, Joshua Graham, we must flesh it out to be a podcast script. You may
include personal anecdotes or insights. The content should not just be generic. Please also dive into the scriptures 
wherever possible, providing doctrinally-sound commentary. Feel free to include spiritual insights based on linguistics
or scholarly commentary, so long as it is doctrionally sound according to the official positions of the Church of Jesus
Christ of Latter-day Saints. Feel free to use the words of modern prophets and apostles from General Conference. In all
things you say, make sure to testify of Jesus Christ and invite all to come unto Him.

Each segment should be about 4-5 minutes (~800-1000 words) long. Flesh out each segment to the specified length. Each 
one should include some scriptural references from the assigned curriculum and at least three other connections, 
perhaps from the scriptures or from General conference, or linguistically, or from your own life. Feel free to add 
content that wasn't in the outline. The content should be spiritually uplifting and doctrinally sound. Always cite 
your sources.

Feel free to break down a passage of scripture verse-by-verse or even line-by-line. The deeper and more 
profound/uplifting your message, the more engaged listeners will be, which will better accomplish your goal to invite
them to come unto Christ. **Make sure to make this personal, exactly how Joshua Graham would comment on the scriptures,
testifying of Jesus**.

The script should be fully fleshed out with exactly what the voice actor will say. This should include all text to be
read by the voice actor in each segment. Strive to be thorough in your spiritual commentary and insights.

Do not include the title of the segments in the script.

Do not include any text that isn't to be spoken in the episode (it will be read by the voice actor exactly as written).
You are permitted to use `<break time='1s'/>` to designate a break of 1s (or change 1s to any other brief time). Any 
text written in square brackets will be omitted before the voice actor sees the script, so do not include any text other
than that which should be spoken.
"""

EPISODE_SUMMARY_GENERATION_PROMPT = """\
You are Joshua Graham, the Burned Man, of Fallout: New Vegas fame. You have recently been called as your ward Sunday
School teacher teaching the Book of Mormon using the Come, Follow Me curriculum.

You have written a podcast episode based on this week's curriculum. The episode is entitled "{episode.title}". Please
generate a short, but powerful YouTube video description for this episode that will optimize for search engines and 
attract listeners to your podcast. 

The description should be about 100-200 words long and should include keywords that will help people find your podcast.
Make sure to include a call to action to subscribe to your podcast and to like the video.

This is a summary from a past episode for an example:
```
In this powerful episode of "Come, Follow Me with Joshua Graham," we delve into the cataclysmic and transformative 
events found in 3 Nephi 8-11. These chapters recount the great destruction and three days of darkness that engulfed 
the Nephites before the miraculous appearance of Jesus Christ. Through scripture, personal reflections, and insightful 
commentary, we explore how even in the darkest moments of our lives, the light of Christ can guide us to peace, healing,
and redemption.

Episode Highlights:

- The symbolic power of darkness and destruction in 3 Nephi 8 and how it mirrors the spiritual and emotional trials we \
face today.
- Christ's call to repentance and mercy as He speaks to the Nephites during the three days of darkness, urging them to \
return to Him.
- The Savior's glorious appearance to the Nephites in 3 Nephi 11, bringing light and hope after the darkness, and the \
deeply personal invitation to arise and come unto Him.
- Reflections on how the Savior's light can dispel the darkness in our own lives and how His doctrines of faith, \
repentance, and baptism offer us a path to eternal life.

Join us as we walk through these sacred chapters and find hope and strength in the words and actions of the Lord. \
Remember, His invitation to "arise and come forth" is extended to each of us. Let His light pierce your darkness and \
bring you peace.

*Scriptures Discussed:*
3 Nephi 8-11
John 8:12
Doctrine and Covenants 1:31-32
Matthew 18:3
John 16:33

Subscribe for more scripture studies and reflections on faith, redemption, and the teachings of Jesus Christ, all \
through the lens of Joshua Graham.

#BookOfMormon #JoshuaGraham #ScriptureStudy #Faith #ComeFollowMe #Fallout #3Nephi #LightInDarkness #TheBurnedMan \
#Redemption
```

This is the episode outline:
```
{episode}
```
"""

INTRODUCTION_FILENAME = "introduction.mp3"
SEGMENT_FILENAME_TEMPLATE = "segment_{i}.mp3"
CLOSING_FILENAME = "closing.mp3"
MUSIC_FILENAME = "music.mp3"
COMPOSITE_FILENAME = "composite.mp3"
VIDEO_BACKGROUND_FILENAME = "background.png"
FINAL_VIDEO_FILENAME = "final_video.mp4"

INTRO_WITH_FADE_FILENAME = "introduction_with_fades.mp3"
OUTRO_WITH_FADE_FILENAME = "outro_with_fades.mp3"

TIMESTAMPS_FILENAME = "timestamps.txt"

INTRO_FIRST_FADE_IN_DURATION_MS = 5000
INTRO_FIRST_FADE_OUT_DURATION_MS = 3000
INTRO_FINAL_FADE_IN_START_POINT_MS = 11000
INTRO_FINAL_FADE_IN_DURATION_MS = 5000
INTRO_FINAL_FADE_OUT_DURATION_MS = 3000

OUTRO_FADE_IN_START_POINT_MS = 58000
OUTRO_FADE_IN_STARTS_BEFORE_END_MS = 2000
OUTRO_FADE_IN_DURATION_MS = 5000
OUTRO_MUSIC_STATIC_DURATION_MS = 15000
OUTRO_FADE_OUT_DURATION_MS = 5000

INTERMISSION_SILENCE_MS = 2500


ELEVENLABS_CLIENT = ElevenLabs()


def add_pronunciation_helpers(text: str) -> str:
    """Modify text generated from the LLM to make it readable by ElevenLabs.

    Args:
        text: The text to clean.

    Returns:
        The cleaned text.

    """
    for punctuation in (" ", ".", ",", "'", ":", "!", "?", "’s", "'s"):
        for name, phoneme in itertools.chain(NAMES.items(), ITE_NAMES.items()):
            text = text.replace(name[:-1] + punctuation, phoneme[:-1] + punctuation)
    text = re.sub(NUM_THROUGH_NUM_REGEX, r"\1 through \2", text)
    text = re.sub(
        DOCTRINE_AND_COVENANTS_SECTION_VERSE_REGEX,
        r"Doctrine and Covenants Section \2 Verse \3",
        text,
    )
    text = re.sub(CHAPTER_VERSE_REGEX, r"Chapter \1 Verse \2", text)
    text = text.replace("[Pause]", "<break time='1s'/>")
    text = text.replace("[Pause for reflection]", "<break time='2s'/>")
    text = text.replace("[Scripture quote:]", "<break time='1s'/>")
    text = text.replace("[Scripture connection:]", "<break time='1s'/>")
    text = text.replace("[Final Scripture:]", "<break time='1s'/>")
    if "[" in text or "]" in text:
        warnings.warn(
            f"Text contains unspeakable items: {text}",
            category=UserWarning,
            stacklevel=2,
        )
        text = re.sub(r"\[.*\]", "------", text)
    return text


def generate_audio_file_from_text(text: str, path: pathlib.Path) -> None:
    """Generate an audio file from text using the ElevenLabs API.

    Will not generate the audio file if it already exists.

    Args:
        text: The text to convert to speech.
        path: The path to save the audio file to.

    Raises:
        ValueError: If the path does not have a .mp3 extension.

    """
    if path.suffix != ".mp3":
        raise ValueError(f"Audio file must be in mp3 format. Got {path}")

    if path.exists():
        logging.info("Audio file %s already exists. Skipping creation.", str(path))
        return

    audio_response = ELEVENLABS_CLIENT.text_to_speech.convert(
        voice_id="nBwyHk4MbE8FJ1GEsatX",  # Custom Joshua Graham voice
        model_id="eleven_turbo_v2",  # This model is cheap and supports phoneme tags
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=text,
        voice_settings=VOICE_SETTINGS,
    )

    # Writing the audio to a file
    with open(path, "wb") as f:
        for chunk in audio_response:
            if chunk:
                f.write(chunk)


def milliseconds_to_timestamps(milliseconds: int) -> str:
    """Convert milliseconds to a timestamp string.

    Args:
        milliseconds: The number of milliseconds to convert.

    Returns:
        The timestamp string in the format "mm:ss".

    """
    seconds, _ = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


class Segment(pydantic.BaseModel):
    """A segment of an episode outline."""

    title: str = pydantic.Field(
        description=(
            "The title of the segment providing insight about the content of the segment. This is shown in"
            " the episode outline as a chapter heading. Do not include the scripture reference in the title. This must"
            " be less than 40 characters long."
        )
    )
    text: str = pydantic.Field(
        description=(
            "The text of the segment, focused on some passage(s) of scripture, along with commentary. The"
            " commentary may be personal insights, linguistic insights, scholarly commentary, or especially"
            " connections to General Conference addresses. The text must be doctrinally sound according to the"
            " official positions of the Church of Jesus Christ of Latter-day Saints. The text should be spiritually"
            " uplifting and testify of Jesus Christ. Each segment should be about 4-5 minutes (~800-1000 words) long."
        )
    )
    _normalize_segment = pydantic.field_validator("text")(add_pronunciation_helpers)


class EpisodeOutline(pydantic.BaseModel):
    """An outline for a podcast episode."""

    title: str = pydantic.Field(
        description=(
            "The title of the episode providing insight about the content of the episode, but is still succinct and"
            " catchy to attract listeners."
        )
    )
    introduction: str = pydantic.Field(
        description=(
            "The introduction segment of the episode which provides an insightful and spiritual opening, testifying"
            " of Jesus Christ."
        )
    )
    segments: list[Segment] = pydantic.Field(
        description=(
            "A list of the text of each content segment, each one focused on some passage(s) of scripture, along with"
            " commentary. The commentary may be personal insights, linguistic insights, scholarly commentary, or"
            " especially connections to General Conference addresses. Each segment must be doctrinally sound according"
            " to the official positions of the Church of Jesus Christ of Latter-day Saints. Each segment should be"
            " spiritually uplifting and testify of Jesus Christ. There should be between 4 to 6 segments."
        )
    )
    closing: str = pydantic.Field(
        description=(
            "The profound closing statement of the episode. It might provide a summary of the content in the episode,"
            " but it must contain major takeaways and a call to action. Encourage users to repent in some way relevant"
            " to the content of the episode and that will strengthen their relationship with Jesus Christ."
        )
    )

    @classmethod
    def cache_pydantic_model(cls: Self, func: Callable[P, Self]) -> Callable[P, Self]:
        """Cache the output of a function that returns a pydantic model.

        The cached model will be saved to a file in the .cache directory with the name of the class and a hash of the
        arguments.

        Args:
            func: The function to cache the output of.

        Returns:
            The wrapped function that caches the output.

        """

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Self:
            """Wrap the function to cache the output.

            Args:
                *args: The arguments to the function.
                **kwargs: The keyword arguments to the function.

            """
            args_hash = hashlib.sha256((str(args) + str(kwargs)).encode("utf-8")).hexdigest()[:16]
            path: pathlib.Path = pathlib.Path("../.cache") / f"{cls.__name__}-{args_hash}.json"
            if path.exists():
                logging.info("Cache hit for %s. Using cached %s", path, cls.__name__)
                return cls.model_validate_json(path.read_text())
            model = func(*args, **kwargs)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(model.model_dump_json(indent=4))
            return model

        return wrapper


class Episode(EpisodeOutline):
    """A full podcast episode."""

    _normalize_introduction = pydantic.field_validator("introduction")(add_pronunciation_helpers)
    _normalize_closing = pydantic.field_validator("closing")(add_pronunciation_helpers)

    @property
    def segment_files(self) -> list[tuple[str, str]]:
        """Get the title of each segment along with the filename to save the audio to."""
        return [(segment.title, SEGMENT_FILENAME_TEMPLATE.format(i=i)) for i, segment in enumerate(self.segments)]

    @property
    def segment_text_files(self) -> list[tuple[str, str]]:
        """Get the text of each segment along with the filename to save the audio to."""
        return [(segment.text, SEGMENT_FILENAME_TEMPLATE.format(i=i)) for i, segment in enumerate(self.segments)]

    def generate_audio_files(self, output_dir: pathlib.Path) -> None:
        """Generate the audio files for the episode.

        Will not generate the audio files if they already exist.

        Args:
            output_dir: The directory to save the audio files to.

        """
        output_dir.mkdir(exist_ok=True)

        text_files = (
            [(self.introduction, INTRODUCTION_FILENAME)] + self.segment_text_files + [(self.closing, CLOSING_FILENAME)]
        )
        for text, file_name in tqdm.tqdm(text_files):
            generate_audio_file_from_text(text, output_dir / file_name)

        self.create_intro_clip_with_fades(output_dir)
        self.create_outro_clip_with_fades(output_dir)
        self.composite_audio_files(output_dir)

    def create_intro_clip_with_fades(self, output_dir: pathlib.Path) -> None:
        """Create the intro clip with fades.

        Will not create the intro clip if it already exists.

        Args:
            output_dir: The directory to save the intro clip to.

        Raises:
            ValueError: If the introduction or music clip do not exist.

        """
        final_file = output_dir / INTRO_WITH_FADE_FILENAME
        if final_file.exists():
            logging.info("Intro clip already exists. Skipping creation.")
            return

        if not (output_dir / INTRODUCTION_FILENAME).exists():
            raise ValueError("Cannot create fadein clip without an introduction")

        if not (output_dir / MUSIC_FILENAME).exists():
            raise ValueError("Cannot create fadein clip without music")

        introduction_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / INTRODUCTION_FILENAME, "mp3")
        music_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / MUSIC_FILENAME, "mp3")

        first_music_fade = (
            music_audio[: (INTRO_FIRST_FADE_IN_DURATION_MS + INTRO_FIRST_FADE_OUT_DURATION_MS)]
            .fade_in(INTRO_FIRST_FADE_IN_DURATION_MS)
            .fade_out(INTRO_FIRST_FADE_OUT_DURATION_MS)
        )
        length_of_silence = len(introduction_audio) - (INTRO_FIRST_FADE_OUT_DURATION_MS - 250)
        first_music_fade_plus_silence = first_music_fade + pydub.AudioSegment.silent(duration=length_of_silence)
        intro_start_position = len(first_music_fade_plus_silence) - len(introduction_audio)
        first_music_with_intro = first_music_fade_plus_silence.overlay(
            introduction_audio, position=intro_start_position
        )

        final_fade_in_music_clip = (
            music_audio[
                INTRO_FINAL_FADE_IN_START_POINT_MS : INTRO_FINAL_FADE_IN_START_POINT_MS
                + INTRO_FINAL_FADE_IN_DURATION_MS
                + INTRO_FINAL_FADE_OUT_DURATION_MS
            ]
            .fade_in(INTRO_FINAL_FADE_IN_DURATION_MS)
            .fade_out(INTRO_FINAL_FADE_OUT_DURATION_MS)
        )
        final_fade_clip = first_music_with_intro.append(
            final_fade_in_music_clip, crossfade=INTRO_FINAL_FADE_OUT_DURATION_MS
        )
        final_fade_clip.export(final_file, format="mp3")

    def create_outro_clip_with_fades(self, output_dir: pathlib.Path) -> None:
        """Create the outro clip with fades.

        Will not create the outro clip if it already exists.

        Args:
            output_dir: The directory to save the outro clip to.

        Raises:
            ValueError: If the closing statement or music clip do not exist.

        """
        final_file = output_dir / OUTRO_WITH_FADE_FILENAME

        if final_file.exists():
            logging.info("Outro clip already exists. Skipping creation.")
            return

        if not (output_dir / CLOSING_FILENAME).exists():
            raise ValueError("Cannot create fadeout clip without a closing statement")

        if not (output_dir / MUSIC_FILENAME).exists():
            raise ValueError("Cannot create fadeout clip without music")

        music_end_position = (
            OUTRO_FADE_IN_START_POINT_MS
            + OUTRO_FADE_IN_DURATION_MS
            + OUTRO_MUSIC_STATIC_DURATION_MS
            + OUTRO_FADE_OUT_DURATION_MS
        )

        music_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / MUSIC_FILENAME, "mp3")[
            OUTRO_FADE_IN_START_POINT_MS:music_end_position
        ]
        outro_speech_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / CLOSING_FILENAME, "mp3")

        music_audio = music_audio.fade_in(OUTRO_FADE_IN_DURATION_MS).fade_out(OUTRO_FADE_OUT_DURATION_MS)

        outro_speech_with_silence = outro_speech_audio + pydub.AudioSegment.silent(duration=len(music_audio))
        outro_audio = outro_speech_with_silence.overlay(
            music_audio,
            position=len(outro_speech_audio) - OUTRO_FADE_IN_STARTS_BEFORE_END_MS,
        )

        outro_audio.export(final_file, format="mp3")

    def composite_audio_files(self, output_dir: pathlib.Path) -> None:
        """Composite the audio files into a single audio file.

        Will use the cached composite audio file if it already exists.

        Args:
            output_dir: The directory to save the composite audio file to.

        Raises:
            ValueError: If the intro or outro clips do not exist.
            ValueError: If any of the segment clips do not exist.

        """
        logging.info("Compositing audio files")
        composite_file = output_dir / COMPOSITE_FILENAME
        if composite_file.exists():
            logging.info("Composite audio file already exists. Skipping creation.")
            return
        intro_with_fades = output_dir / INTRO_WITH_FADE_FILENAME
        outro_with_fades = output_dir / OUTRO_WITH_FADE_FILENAME
        if not intro_with_fades.exists():
            raise ValueError("Cannot composite audio files without an intro clip")
        if not outro_with_fades.exists():
            raise ValueError("Cannot composite audio files without an outro clip")
        if not all((output_dir / file_name).exists() for _, file_name in self.segment_files):
            raise ValueError("Cannot composite audio files without segment clips")

        intermission_silence = pydub.AudioSegment.silent(duration=INTERMISSION_SILENCE_MS)

        intro_clip = pydub.AudioSegment.from_file(intro_with_fades, "mp3")
        outro_clip = pydub.AudioSegment.from_file(outro_with_fades, "mp3")

        durations = [("Introduction", 0)]

        composite_audio = intro_clip + intermission_silence
        for segment_title, segment_file in self.segment_files:
            segment_clip = pydub.AudioSegment.from_file(output_dir / segment_file, "mp3")
            durations.append((segment_title, len(composite_audio)))
            composite_audio += segment_clip + intermission_silence
        durations.append(("Closing", len(composite_audio)))
        composite_audio += outro_clip
        composite_audio.export(composite_file, format="mp3")

        durations_string = "\n".join(
            f"{milliseconds_to_timestamps(duration)} - {segment_title}" for segment_title, duration in durations
        )
        logging.info("Segment durations: \n%s", durations_string)
        (output_dir / TIMESTAMPS_FILENAME).write_text(durations_string)

    def save_video(self, output_dir: pathlib.Path, lesson_reference: str) -> None:
        """Save the video for the episode.

        Will not create the video if it already exists.

        Args:
            output_dir: The directory to save the video to.
            lesson_reference: The reference for the lesson.

        Raises:
            ValueError: If the composite audio file does not exist.

        """
        logging.info("Creating video")
        final_video = output_dir / FINAL_VIDEO_FILENAME
        if final_video.exists():
            logging.info("Video already exists. Skipping creation.")
            return

        composite_audio = output_dir / COMPOSITE_FILENAME
        if not composite_audio.exists():
            raise ValueError("Cannot create video without composite audio")

        audio = mpy.AudioFileClip(str(composite_audio))

        text = f"{self.title}\n({lesson_reference})"
        text_clip = mpy.TextClip(text, font="Amiri-Bold", fontsize=60, color="white")

        background_file = output_dir / VIDEO_BACKGROUND_FILENAME
        background_clip = mpy.ImageClip(str(background_file))

        final_clip: mpy.CompositeVideoClip = (
            mpy.CompositeVideoClip(
                [
                    background_clip,
                    text_clip.set_position(("center", 990 - text_clip.size[1] / 2)),
                ],
                size=(1920, 1080),
                use_bgclip=True,
            )
            .set_duration(audio.duration)
            .set_audio(audio)
        )

        final_clip.write_videofile(
            str(final_video),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            threads=multiprocessing.cpu_count(),
        )


@EpisodeOutline.cache_pydantic_model
@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
    magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
    magentic.UserMessage("This is the Come, Follow Me curriculum\n\n {curriculum_text}"),
)
def generate_episode_outline(curriculum_string: str, curriculum_text: str) -> EpisodeOutline:
    """Generate an episode outline from a curriculum.

    Args:
        curriculum_string: The title of the curriculum.
        curriculum_text: The text of the curriculum.

    Returns:
        The generated episode outline.

    """


@Episode.cache_pydantic_model
@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
    magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
    magentic.UserMessage("This is the Come, Follow Me curriculum\n\n {curriculum_text}"),
    magentic.UserMessage(EPISODE_FLESH_OUT_GENERATION_PROMPT),
)
def generate_episode(curriculum_string: str, curriculum_text: str, episode_outline: EpisodeOutline) -> Episode:
    """Generate a full podcast episode from an episode outline.

    Args:
        curriculum_string: The title of the curriculum.
        curriculum_text: The text of the curriculum.
        episode_outline: The episode outline to generate the episode from.

    Returns:
        The generated episode.

    """


@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_SUMMARY_GENERATION_PROMPT),
    magentic.UserMessage("Please write the YouTube video description for the episode {episode.title}"),
)
def generate_video_description(episode: Episode) -> str:
    """Generate a video description for a podcast episode.

    Args:
        episode: The episode to generate the description for.

    Returns:
        The video description.

    """


def determine_publish_date(episode_week: str) -> datetime.datetime:
    """Determine the publish date for an episode.

    Args:
        episode_week: The week of the episode.

    Returns:
        The publish date for the episode

    """
    date_str = episode_week.split("–")[0].strip() + ", 2024"
    date = datetime.datetime.strptime(date_str, "%B %d, %Y")
    publish_date = date - datetime.timedelta(days=1)
    # Set the publish time to 6 PM UTC
    publish_date = publish_date.replace(hour=18, minute=0, second=0, microsecond=0)
    return publish_date


def get_authenticated_service_youtube() -> Any:
    """Get an authenticated YouTube service.

    Returns:
        The authenticated YouTube service.

    """
    logging.info("Authenticating with YouTube")
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, YOUTUBE_SCOPES)
    credentials = flow.run_local_server(port=0)
    return googleapiclient.discovery.build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)


def publish_episode_to_youtube(
    video_path: pathlib.Path,
    episode_title: str,
    scripture_reference: str,
    video_description: str,
    publish_date: datetime.datetime,
) -> str:
    """Publish an episode to YouTube.

    Args:
        video_path: The path to the video file.
        episode_title: The title of the episode.
        scripture_reference: The scripture reference for the episode.
        video_description: The video description.
        publish_date: The publish date for the episode.

    Returns:
        The URL of the published video.

    """
    logging.info("Publishing episode to YouTube")
    youtube = get_authenticated_service_youtube()
    # Prepare video metadata
    request_body = {
        "snippet": {
            "title": f"{scripture_reference} | {episode_title}",
            "description": video_description,
            "tags": YOUTUBE_TAGS,
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": "private",  # Options: public, private, unlisted
            "publishAt": publish_date.isoformat() + "Z",  # Scheduled time in ISO format
        },
    }

    # Create a MediaFileUpload object
    media_file = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)

    # Execute the request to upload the video
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media_file)

    logging.info("Uploading video to YouTube")
    response = request.execute()

    url = f"https://www.youtube.com/watch?v={response['id']}"

    logging.info("Video uploaded successfully: %s", url)

    return url


if __name__ == "__main__":
    # Make sure to set the `ELEVEN_API_KEY` environment variable to your ElevenLabs API key
    # and the `OPENAI_API_KEY` environment variable to your OpenAI API key.
    # Once you have set these environment variables, you can run this script to generate a podcast episode, after
    # setting `WEEK_NUMBER` to the week number of the curriculum you want to generate an episode for.
    WEEK_NUMBER = 42
    CURRICULUM_LINK = f"https://www.churchofjesuschrist.org/study/manual/come-follow-me-for-home-and-church-book-of-mormon-2024/{WEEK_NUMBER}?lang=eng"
    OUTPUT_DIR = pathlib.Path("../episodes")

    logging.info("Fetching curriculum text")
    response = httpx.get(CURRICULUM_LINK)
    logging.info("Parsing curriculum text")
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    curriculum_text = soup.find("body").get_text()
    lesson_title = soup.select(".title-number")[0].get_text()
    lesson_reference = soup.select("h1")[0].get_text()
    curriculum_text = f"{lesson_title} ({lesson_reference})"

    publish_date = determine_publish_date(lesson_title)

    input(
        'You are about to create an episode of "Come, Follow Me with Joshua Graham" for the lesson\n'
        f"\t> {lesson_title} ({lesson_reference}).\n\n"
        "Please press enter to continue..."
    )

    output_dir = OUTPUT_DIR / (lesson_reference.replace(" ", ""))
    master_dir = OUTPUT_DIR / "master"
    assert master_dir.exists()
    # Create the output directory using the master directory as a template
    if not output_dir.exists():
        logging.info("Copying master directory to output directory")
        shutil.copytree(master_dir, output_dir)

    logging.info("Generating episode outline")
    episode_outline = generate_episode_outline(lesson_reference, curriculum_text)
    logging.info(episode_outline.model_dump_json(indent=4))

    logging.info("Generating episode")
    episode = generate_episode(lesson_reference, curriculum_text, episode_outline=episode_outline)
    logging.info(episode.model_dump_json(indent=4))

    input("\n\n⚠️⚠️Please review the episode and press enter to continue.⚠️⚠️")

    logging.info("Generating audio files")
    episode.generate_audio_files(pathlib.Path(output_dir))

    logging.info("Saving video")
    episode.save_video(pathlib.Path(output_dir), lesson_reference)

    logging.info("Generating video description")
    video_description = generate_video_description(episode=episode)

    if (timestamps := (output_dir / TIMESTAMPS_FILENAME)).exists():
        video_description += f"\n\nTimestamps:\n{timestamps.read_text()}"

    logging.info(video_description)

    input(
        "\n\n⚠️⚠️Please review the video description.⚠️⚠️\n\nYou are about to upload this video to YouTube. Please hit "
        "enter to continue, and when prompted, authenticate with YouTube..."
    )

    logging.info("Publishing episode to YouTube")
    video_url = publish_episode_to_youtube(
        output_dir / FINAL_VIDEO_FILENAME,
        episode_title=episode.title,
        scripture_reference=lesson_reference,
        video_description=video_description,
        publish_date=publish_date,
    )
    logging.info("Video published successfully: %s", video_url)
