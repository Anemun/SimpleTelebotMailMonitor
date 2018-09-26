#!/usr/bin/python3

import imaplib
import logging
import smtplib
import argparse, sys
import time
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



# send a message every hour with unique id (yearmonthdayhour)
# monitor incoming messages for that message
# past 45min send alarm messages

def debugLog(message):
    if debugEnabled:
        print(message)
        sys.stdout.flush()

lastSendTime = datetime.now()
lastDateTimeString = ""
lastRcv = ""
timeFormat = '%Y%m%d%H%M'
whaitingForResponse = False
debugEnabled = True

message = "Мониторинг хождения почты до/от {0} запущен.".format(toMailbox)
url = 'https://api.telegram.org/bot{0}/sendMessage?chat_id={1}&text={2}'.format(botToken, chatId, message)
debugLog("{0}: monitor started. Checking mail flow from {1} to {2} and back".format(datetime.now(), mailboxLogin, toMailbox))
try:
    requests.get(url.encode('UTF-8'))
except Exception as err:
    debugLog("{0}: ERROR! {1}".format(datetime.now(),err))


def SendMail():
    global lastSendTime, lastDateTimeString

    TO = toMailbox
    SUBJECT = lastDateTimeString
    TEXT = 'testing message flow in and out of {0}'.format(mailDomain)
    
    debugLog("{0}: Trying to send mail".format(datetime.now()))
    try:
        server = smtplib.SMTP(smtpSrv, 25)
        server.ehlo()
        server.starttls()
        server.login(mailboxLogin, mailboxPassword)
        debugLog("{0}: login successfull, sending...".format(datetime.now()))

        BODY = '\r\n'.join(['To: %s' % TO,
                            'From: %s' % mailboxLogin,
                            'Subject: %s' % SUBJECT,
                            '', TEXT])

        
        server.sendmail(mailboxLogin, [TO], BODY)
        debugLog('{0}: email sent to {1}, subject: {2}'.format(datetime.now(), TO, SUBJECT))
        lastSendTime = datetime.now()
    except smtplib.SMTPException as err:
        debugLog("{0}: ERROR! {1}".format(datetime.now(),err))
        message = "ALARM!!! Не получается отправить тестовое письмо на {0}!\n\n {1}".format(toMailbox, err)
        url = 'https://api.telegram.org/bot{0}/sendMessage?chat_id={1}&text={2}'.format(botToken, chatId, message)
        debugLog("{0}: ALARM!!! Can't send monitor email from {1} to {2}!!! {3}".format(datetime.now(), mailboxLogin, toMailbox, err))
        try:
            requests.get(url.encode('UTF-8'))
        except Exception as err:
            debugLog("{0}: ERROR! {1}".format(datetime.now(),err))

    server.quit()


def GotMail():        
    debugLog("{0}: Trying to read mail (5 attempts)".format(datetime.now()))
    gotTheMessage = False
    for i in range(0,5):  
        try: 
            mailbox = imaplib.IMAP4_SSL(imapSrv)
            debugLog("{0}: attempt {1}".format(datetime.now(),i+1))
            mailbox.login(mailboxLogin, mailboxPassword)
            mailbox.list()                                              # Выводит список папок в почтовом ящике.
            mailbox.select("inbox")                                     # Подключаемся к папке "входящие".
            #pylint: disable=unused-variable
            result, data = mailbox.search(None, "ALL")
            ids = data[0]                                               # Получаем строку номеров писем
            debugLog("{0}: login successfull, searching...".format(datetime.now()))

            id_list = ids.split()                                       # Разделяем ID писем
            id_list_last_five = id_list[-5:]                            # Последние 5 ID
            
            global lastRcv
            
            debugLog("{0}: checking mail on {1}, looking for subject {2}-{3}"
                                .format(datetime.now(), mailboxLogin, mailIdentity, lastDateTimeString))
            for i in id_list_last_five:                                 
                email_id = i
                result, data = mailbox.fetch(email_id, "(RFC822)")
                raw_email = str(data[0][1])                             # Тело письма в необработанном виде
                eml = raw_email.split('Subject: ')[1].split('\\r')[0].split('-')    # вычленяем тему письма, разбиваем её
                timeString = eml[1]
                
                # первая часть темы должны быть "received" а затем номер отправки
                if (eml[0] == mailIdentity) and \
                    (timeString == lastDateTimeString):
                    gotTheMessage = True
                    lastRcv = timeString
                    debugLog("{0}: found mail.".format(datetime.now()))
            
            mailbox.close()
            mailbox.logout()
            debugLog("{0}: logout.".format(datetime.now()))
        except Exception as err:
            debugLog(err)
            message = "ALARM!!! Не получается получить список писем с ящика мониторинга ({0})!\n\n {1}".format(mailboxLogin, err)
            url = 'https://api.telegram.org/bot{0}/sendMessage?chat_id={1}&text={2}'.format(botToken, chatId, message)
            debugLog("{0}: ALARM!!! Can't check for email from {1} to {2}!!! {3}".format(datetime.now(), toMailbox, mailboxLogin, err))
            try:
                requests.get(url.encode('UTF-8'))
            except Exception as err:
                debugLog("{0}: ERROR! {1}".format(datetime.now(), err))
            continue
        break
    return gotTheMessage

while True:
    if not whaitingForResponse:
        if datetime.now().minute <= 5:          # если текущее время 5 минут любого часа, отправляем письмо
            debugLog("\n{0}: it's time to send mail!".format(datetime.now()))
            lastDateTimeString = str(datetime.now().strftime(timeFormat))
            whaitingForResponse = True
            SendMail()

    while whaitingForResponse:                  # ждём ответа с интервалом в 3 минуты        
        debugLog("{0}: checking mail...".format(datetime.now()))
        if GotMail():                           # если мы получили ответное письмо
            debugLog("{0}: got mail, everything fine! msgNumber: {1}".format(datetime.now(), lastRcv))
            whaitingForResponse = False

        elif datetime.now().minute >= 45:       # если не получили и время уже 45 минут
            whaitingForResponse = False
            message = "ALARM!!! Не ходит почта в {0}!".format(mailDomain)
            debugLog("{0}: ALARM!!! It's 45min already and sill no mail received (it must be msgNumber {1})".format(datetime.now(), lastDateTimeString))
            url = 'https://api.telegram.org/bot{0}/sendMessage?chat_id={1}&text={2}'.format(botToken, chatId, message)
            try:
                requests.get(url.encode('UTF-8'))
            except Exception as err:
                debugLog("{0}: ERROR! {1}".format(datetime.now(), err))
            
        else:
            debugLog("{0}: there is no mail yet... (looking for msgNumber {1}). Retry in 3 minutes".format(datetime.now(), lastDateTimeString))
        time.sleep(180)
    
    time.sleep(30)
