#!/usr/bin/python3

import imaplib
import logging
import smtplib
import argparse, sys
import time
import random
from enum import Enum
from datetime import datetime

import requests

parser=argparse.ArgumentParser()
parser.add_argument('--fromMailbox', help='mailbox from which mail will be sent')
parser.add_argument('--fromMailboxPass', help='password for mailbox from which mail will be sent')
parser.add_argument('--smtpServer', help='smtp server for FromMailbox')
parser.add_argument('--imapServer', help='imap server for FromMailbox')
parser.add_argument('--toMailbox', help='mailbox to which mail will be sent')
parser.add_argument('--botToken', help='telegram bot token to whom notifications will be sent')
parser.add_argument('--botChatId', help='telegram bot chat ID to which notifications will be sent')
parser.add_argument('--subjectCode', help='code to identify returned email')
args=parser.parse_args()

toMailbox = args.toMailbox
mailDomain = toMailbox.split('@')[1]
mailboxLogin = args.fromMailbox
mailboxPassword = args.fromMailboxPass
smtpSrv = args.smtpServer
imapSrv = args.imapServer
mailIdentity = args.subjectCode          
botToken = args.botToken  
chatId = args.botChatId

version = "2.0.7"

""" 2.0 code

states: init, send, listen
init (also on startup):
    randomly choose delay (1-90 seconds)
    check for telegram
send:
    try to send mail (5 attemps) -> if unsuccefull, throw alarm
    (with unique id - yearmonthdayhourminutesecond)
listen:
    every 30 seconds check for returned mail
    if past 5 minutes - alarm
 

end of 2.0 code """

debugEnabled = True

class State(Enum):
    init = 0
    send = 1
    listen = 2

def debugLog(message):
    if debugEnabled:
        print("{0}: {1}".format(datetime.now(), message))
        sys.stdout.flush()

def sendTelegramMsg(message):    
    url = 'https://api.telegram.org/bot{0}/sendMessage?chat_id={1}&text={2}'.format(botToken, chatId, message)
    try:
        requests.get(url.encode('UTF-8'))
    except Exception as err:
        debugLog("ERROR! {0}".format(err))

state = State.init
timeFormat = '%Y%m%d%H%M%S'
lastSendTime = None
timecode = ""
lastReceivedTime = None

sendTelegramMsg("Мониторинг хождения почты до/от {0} запущен. (v{1})".format(toMailbox, version))
debugLog("monitor started. Checking mail flow from {0} to {1} and back. (v{2})".format(mailboxLogin, toMailbox, version))

while True:    
    if state is State.init:
        gotTheMessage = False
        delay = random.randint(1, 90)
        debugLog("init stage.. delaying for {0} seconds".format(delay))
        time.sleep(delay)
        timecode = str(datetime.now().strftime(timeFormat))
        state = State.send
    if state is State.send:
        TO = toMailbox
        SUBJECT = timecode
        TEXT = 'testing message flow in and out of {0}'.format(mailDomain)
        for attempt in range(1, 6):
            debugLog("Trying to send mail (attempt {0} of 5)".format(attempt))
            try:
                server = smtplib.SMTP(smtpSrv, 25)
                server.ehlo()
                server.starttls()
                server.login(mailboxLogin, mailboxPassword)
                debugLog("login successfull, sending...")
                BODY = '\r\n'.join(['To: %s' % TO,
                                    'From: %s' % mailboxLogin,
                                    'Subject: %s' % SUBJECT,
                                    '', TEXT])                
                server.sendmail(mailboxLogin, [TO], BODY)
                debugLog('email sent to {0}, subject: {1}'.format(TO, SUBJECT))
                lastSendTime = datetime.now()
                state = State.listen
            except smtplib.SMTPException as err:
                if (attempt == 5):
                    sendTelegramMsg("ALARM!!! Не получается отправить тестовое письмо на {0}!\n\n {1}".format(toMailbox, err))
                    debugLog("ALARM!!! Can't send monitor email from {0} to {1}!!! {2}".format(mailboxLogin, toMailbox, err))
                    state = State.init
                    break  
                else:                                      
                    time.sleep(10)
                    continue
            break
        server.quit()
    if state is State.listen:
        for attempt in range(1,6):  
            debugLog("Trying to read mail (attempt {0} of 5)".format(attempt))
            try: 
                mailbox = imaplib.IMAP4_SSL(imapSrv)
                mailbox.login(mailboxLogin, mailboxPassword)
                mailbox.list()                                              # Выводит список папок в почтовом ящике.
                mailbox.select("inbox")                                     # Подключаемся к папке "входящие".
                #pylint: disable=unused-variable
                result, data = mailbox.search(None, "ALL")
                ids = data[0]                                               # Получаем строку номеров писем
                debugLog("login successfull, searching...")
                id_list = ids.split()                                       # Разделяем ID писем
                id_list_last_five = id_list[-5:]                            # Последние 5 ID 
                debugLog("checking mail on {0}, looking for subject {1}-{2}"
                                    .format(mailboxLogin, mailIdentity, timecode))
                for i in id_list_last_five:                                 
                    email_id = i
                    result, data = mailbox.fetch(email_id, "(RFC822)")
                    raw_email = str(data[0][1])                             # Тело письма в необработанном виде
                    eml = raw_email.split('Subject: ')[1].split('\\r')[0].split('-')    # вычленяем тему письма, разбиваем её
                    timeString = eml[1]
                    #debugLog(eml)
                    
                    # первая часть темы должны быть "receivedXXX" а затем номер отправки
                    if (eml[0] == mailIdentity) and (eml[1] == timecode):
                        gotTheMessage = True
                        lastRcv = timeString
                        debugLog("found mail.")
                        break
                
                mailbox.close()
                mailbox.logout()
                debugLog("logout. wait for 30sec")
            except Exception as err:   
                if (attempt == 5):
                    sendTelegramMsg("ALARM!!! Не получается получить список писем с ящика мониторинга ({0})!\n\n {1}".format(mailboxLogin, err))                    
                    debugLog("ALARM!!! Can't check for email from {0} to {1}!!! {2}".format(toMailbox, mailboxLogin, err))                    
                    state = State.init
                    break
                else:
                    time.sleep(15)
                    continue
            break
    
    diff = datetime.now() - lastSendTime
    if gotTheMessage == True:
        debugLog("waiting for 180 seconds till next cycle")
        time.sleep(600)
        state = State.init 
    elif gotTheMessage == False and diff.seconds >= 300:
        sendTelegramMsg("ALARM!!! Не ходит почта в {0}!".format(mailDomain))
        debugLog("{0}: ALARM!!! It's 45min already and sill no mail received (it must be msgNumber {1})".format(datetime.now(), timecode))
        state = State.init        
