import imaplib
import os
import sys
import email
import zipfile
import gzip
import glob
import logging
from parse_report import dmarc_rua_parser



zipfiles = []
gzfiles = []
packdir = "packed/"
unpackdir = "unpacked/"


def connect_and_find_new_reports(hostname, username, password):
    # Connect to the server
    print "[*] Connecting to the IMAP server"
    logging.info('Connecting to IMAP server %s', hostname)
    try:
        imap = imaplib.IMAP4_SSL(hostname)
    except:
        print "\t[-] Connection to the IMAP server failed - check your settings"
        logging.error('Something went wrong when connecting to the IMAP server.', exc_info=True)

    # Login to our account
    try:
        imap.login(username, password)
    except:
        print "\t[-] Connection to the IMAP server failed - check your settings"
        logging.error('Something went wrong when connecting to the IMAP server.', exc_info=True)

    # Select the Inbox
    try:
        imap.select('INBOX')
    except:
        print "\t[-] Connection to the IMAP server failed - check your settings"
        logging.error('Something went wrong when connecting to IMAP server.', exc_info=True)

    # Look for unread emails
    print "\t[+] Checking for unread emails"
    logging.info('Checking for unread emails')
    typ, unread_emails = imap.search(None, 'UNSEEN')

    # Loop through emails and grab attachments
    if len(unread_emails[0].split()) > 0:
        print("\t[+] Parsing attchments")
        logging.info('Parsing attachments')
    for number in unread_emails[0].split():
        # Get the current email
        typ, data = imap.fetch(number, '(RFC822)')
        # message = email.message_from_bytes(data[0][1]) <--- Python3
        message = email.message_from_string(data[0][1])
        #
        for part in message.walk():
            attach_name = part.get_filename()
            if attach_name:
                attach_dest = packdir + attach_name
                if not (attach_name.endswith('.zip') or attach_name.endswith('.gz')):
                    logging.info('Ignoring non-zip or non-gz attachment "{0}"'.format(attach_name))
                    continue
                # if not attach_name.endswith('.gz'):
                #     print("Don't have a .gz file attached")
                #     # log('ignoring non-zip attachment "{0}"'.format(attach_name))
                #     passdiur
                try:
                    attach_data = email.base64mime.decode(part.get_payload())
                except binascii.Error:
                    # print("Could not decode attachment")
                    logging.error('Could not decode attachment "{0}"'.format(attach_name))
                    continue

                with open(attach_dest, "wb") as fd:
                    try:
                        fd.write(attach_data)
                    except:
                        logging.error('Could not write %s', attach_data, exc_info=True)
                if attach_name.endswith('.zip'):
                    zipfiles.append(attach_dest)
                else:
                    gzfiles.append(attach_dest)
    imap.close()
    imap.logout()
    logging.info('Disconnected from IMAP server')
    for file in glob.glob('packed/*.gz'):
        print(file)
    print "[*] Disconnected from IMAP server"
    return imap

def extract_files(target, parse_only_failed):
    if not os.path.exists(unpackdir):
        try:
            os.makedirs(unpackdir)
        except:
            logging.error('Could not create directory', exc_info=True)
            print("\t[-] Could not create a necessary directory.")
            sys.exit(1)
    if not os.path.exists(packdir):
        try:
            os.makedirs(packdir)
        except:
            logging.error('Could not create directory', exc_info=True)
            print("\t[-] Could not create a necessary directory.")
            sys.exit(1)

    files_to_parse = False
    if len(zipfiles) > 0:
        for file in zipfiles:
            try:
                zip_ref = zipfile.ZipFile(file, 'r')
            except:
                # print("Something went wrong when opening the file")
                logging.error('Something went wrong when opening a file', exc_info=True)
                continue
            zip_ref.extractall(unpackdir)
            zip_ref.close()
            os.remove(file)
            files_to_parse = True
    else:
        # print("No .zip files")
        pass


    if len(gzfiles) > 0:
        for file in gzfiles:
            # Generate the new location / filename for the decompressed file. Clunky? Hell yeah!
            directory, filename = os.path.split(file)
            xmlfile, extension = os.path.splitext(filename)
            newfilelocation = unpackdir + xmlfile
            # Decompress the gz file
            try:
                compressedfile = gzip.GzipFile(file)
            except:
                # print("Something went wrong when opening the file")
                logging.error('Something went wrong when opening a file', exc_info=True)
                continue
            content = compressedfile.read()
            compressedfile.close()

            # Write the new decompressed file in the unpack directory
            decompressedfile = open(newfilelocation, 'wb')
            try:
                decompressedfile.write(content)
            except:
                logging.error('Something went wrong when saving a file', exc_info=True)
            decompressedfile.close()

            # Delete the compressed file
            os.remove(file)
            files_to_parse = True
    else:
        # print("No .gz files")
        pass

    if files_to_parse:
        print "[*] Parsing files and publishing to Splunk"
        logging.info('Starting to parse files.')
        send_files_to_parser(target, parse_only_failed)


def send_files_to_parser(target, parse_only_failed):
    # print("Starting to parse files")
    for file in glob.glob('unpacked/*.xml'):
        dmarc_rua_parser(file, target, parse_only_failed)
        os.remove(file)


if __name__ == '__main__':
    imap = connect_and_find_new_reports(verbose=True)
    extract_files(target)

