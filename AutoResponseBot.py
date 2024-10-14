import os
import requests
import gpt_2_simple as gpt2
from datetime import datetime
from twitchAPI.pubsub import PubSub
from twitchAPI.twitch import Twitch
from twitchAPI.types import AuthScope
from twitchAPI.oauth import UserAuthenticator
from ibm_watson import TextToSpeechV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from pprint import pprint
from uuid import UUID
import time
import socket
import select
import nest_asyncio
from emoji import demojize
nest_asyncio.apply()
import simpleaudio as sa
import re

#Set up a job list, a lock, and a timer.
current_time = time.perf_counter()

#Set up model for GPT2-Simple
model_name = "355M"
if not os.path.isdir(os.path.join("models", model_name)):
	print(f"Downloading {model_name} model...")
	gpt2.download_gpt2(model_name=model_name) 

#Create IBM connection
authenticator = <IAMINSTANCE>
text_to_speech = TextToSpeechV1(
    authenticator=authenticator
)

#Service URL for IBM TTS
text_to_speech.set_service_url(<SERVICEURL>)

# create instance of twitch API
twitch = <TWITCHINSTANCE>
twitch.authenticate_app([])

target_scope = [AuthScope.CHANNEL_SUBSCRIPTIONS, AuthScope.CHANNEL_READ_REDEMPTIONS]
auth = UserAuthenticator(twitch, target_scope, force_verify = False)

# this will open your default browser and prompt you with the twitch verification website
token, refresh_token = auth.authenticate()

# add User authentication
twitch.set_user_authentication(token, target_scope, refresh_token)

generationList = list()

twitch.set_user_authentication(token, [AuthScope.CHANNEL_SUBSCRIPTIONS, AuthScope.CHANNEL_READ_REDEMPTIONS], refresh_token)
user_id = twitch.get_users(logins=[<USERNAME>])['data'][0]['id']

# starting up PubSub
pubsub = PubSub(twitch)
pubsub.start()

sess = gpt2.start_tf_sess()
gpt2.load_gpt2(sess,model_name=model_name)
#generates a message based on the provided data from the twitch API. This method is messy and needs comments and cleaning.

def respond(prefix):
    generatedText = gpt2.generate(sess,
            model_name=model_name,
            prefix=prefix,
            length=75,
            temperature=.8,
            nsamples=3,
            batch_size=3,
            return_as_list=True,
            truncate='\n',
            include_prefix=False
            )
    pprint("--------FINISHED TEXT GENERATION--------")
    pprint(generatedText)
    goodText = list()
    for sample in generatedText:

       # Here I have filters for words I don't want the AI using in stream. I have removed them for the reason of not having those push up to a public repo, but please filter AI output.

        goodText.append(sample)

        generatedText = goodText[0]
        for sample in goodText[1:]:
            if len(sample) > len(generatedText):
                generatedText = sample

    if type(generatedText) is type(list):
        generatedText = "I tried to say something bad..."

    return generatedText

def generateText():
    data = generationList.pop()
    if(data.get("sub_message", -1) != -1):

        dataBody = data.get("sub_message").get("message","")
        dataSender = data.get("display_name","anon")

        if(data.get("is_gift",False) == False):
            prefix = dataSender + ": " + dataBody + "\n\nalexthestreamai: "
        else:
            prefix = dataSender + " Just Gifted a Sub: " + dataBody + "\n\nalexthestreamai:  "
            #Start Sess

        with open("AlexOperation.txt", "w") as txt_file:
            txt_file.write("Alex is Thinking of a response to " + dataSender + "...")
        with open("MessageResponses.txt", "a") as save_file:
            save_file.write(prefix)

        generatedText = respond(dataBody)

        with open("MessageResponses.txt", "a") as save_file:
            save_file.write("alexthestreamai: " + generatedText + "\n")


        if(data.get("is_gift")):
            generatedText = dataSender + " just gifted " + data.get("recipient_display_name", "someone") + " a sub! " + dataSender + " said: " + dataBody + " response: " + generatedText
        else:
            generatedText = dataSender + " just subbed! " + dataSender + " said: " + dataBody + " response: "  + generatedText

        with open("AlexOperation.txt", "w") as txt_file:
            txt_file.write("Alex is responding to " + dataSender + "!")

        print()
        print(generatedText)
        print()

        #generate and play audio
        with open('Bot_Response.wav', 'wb') as audio_file:
            audio_file.write(
                text_to_speech.synthesize(
                    generatedText,
                    voice='en-US_AllisonV3Voice',
                    accept='audio/wav'        
                ).get_result().content)

        filename = 'Bot_Response.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        play_obj.wait_done()  # Wait until sound has finished playing
    else:
        if (data.get("data").get("redemption",-1) != -1 and data.get("data").get("redemption").get("reward").get("title") == "Send A Message to Alex, our Stream AI"):
            dataBody = data.get("data").get("redemption").get("user_input","")
            dataSender = data.get("data").get("redemption").get("user").get("display_name","someone")


            prefix = dataSender + ": " + dataBody + " \n"
                #Start Sess

            with open("AlexOperation.txt", "w") as txt_file:
                txt_file.write("Alex is Thinking of a response to " + dataSender + "...")
            with open("MessageResponses.txt", "a") as save_file:
                save_file.write(prefix)

            prefix = prefix + "alexthestreamai: "
            generatedText = respond(dataBody)

            with open("MessageResponses.txt", "a") as save_file:
                save_file.write("alexthestreamai:" + generatedText + "\n")

            generatedText = dataSender + " Said: " + dataBody + " response: " + generatedText

            print()
            print(generatedText)
            print()

            #generate and play audio
            with open('Bot_Response.wav', 'wb') as audio_file:
                audio_file.write(
                    text_to_speech.synthesize(
                        generatedText,
                        voice='en-US_AllisonV3Voice',
                        accept='audio/wav'        
                    ).get_result().content)

            with open("AlexOperation.txt", "w") as txt_file:
                txt_file.write("Alex is responding to " + dataSender + "!")

            filename = 'Bot_Response.wav'
            wave_obj = sa.WaveObject.from_wave_file(filename)
            play_obj = wave_obj.play()
            play_obj.wait_done()  # Wait until sound has finished playing

#Callback for subscriptions message
def callback_sub(uuid: UUID, data: dict) -> None:
    pprint('--------RECEIVED DATA--------')
    generationList.append(data)
    pprint(data)

#Callback for points
def callback_points(uuid: UUID, data: dict) -> None:
    pprint('--------RECEIVED DATA--------')
    generationList.append(data)

# you can either start listening before or after you started pubsub.
uuid = pubsub.listen_channel_subscriptions(user_id, callback_sub)
uuid = pubsub.listen_channel_points(user_id, callback_points)



#variable for changing the value when Alex is functioning
Vibing = False

#variable for event timer
event_messages = 3 #number of messages before event triggers

server = "irc.chat.twitch.tv"
port = 6667
nickname = <NICKNAME>
token = <TOKEN>
channel = <CHANNEL>
messages = 0
count = 0

#Connect to twitch chat for the message bot
sock = socket.socket()
sock.connect((server, port))

sock.send(f"PASS {token}\n".encode('utf-8'))
sock.send(f"NICK {nickname}\n".encode('utf-8'))
sock.send(f"JOIN #{channel}\n".encode('utf-8'))


def chat(sock, msg):
    """
    Send a chat message to the server.
    Keyword arguments:
    sock -- the socket over which to send the message
    msg  -- the message to be sent
    """
    sock.send("PRIVMSG #{} :{}\r\n".format(channel, msg).encode("utf-8"))

while True:
      ready = select.select([sock],[],[],3)
      if ready[0]:
        resp = sock.recv(2048).decode('utf-8')
        print(resp)
        if resp.startswith('PING'):
            sock.send("PONG\n".encode('utf-8'))
        elif len(resp) > 0:
            if count >= 2:
                try:
                    username, channel, message = re.search(
                        ':(.*)\!.*@.*\.tmi\.twitch\.tv PRIVMSG #(.*) :(.*)', resp
                    ).groups()
                    message = message.strip()
                    with open('chatLog.txt', 'a') as txt_file:
                        print(username + ": " + message + "\n")
                        txt_file.write(username + ": " + message + "\n")
                    messages += 1
                except:
                    print("Got a bad resp")
            else:
                count += 1


      if len(generationList) > 0:
          pprint("--------STARTING AUTO RESPONSE--------")
          Vibing = False
          generateText()
          pprint("--------FINISHED AUTO RESPONSE--------")
      elif messages >= event_messages:
          
          messages = 0
          chatLog = open("chatLog.txt")
          chatLog = chatLog.readlines()
          chatLog = chatLog[len(chatLog) - 10:]
          prefix = ""

          for line in chatLog:
              prefix += line
          generatedText = respond(prefix).split(':')[1]

          with open("chotLog.txt", "a") as save_file:
              save_file.write("AlexTheStreamAI: " + generatedText + "\n")
          chat(sock,generatedText)
          print(generatedText)

      elif not Vibing:
          with open("AlexOperation.txt", "w") as txt_file:
            txt_file.write("Alex is vibing.")         
          Vibing = True


# you do not need to unlisten to topics before stopping but you can listen and unlisten at any moment you want.
pubsub.unlisten(uuid)
pubsub.stop()


