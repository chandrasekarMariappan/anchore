import os
import sys
import requests
import re
import json
import time
import anchore.anchore_auth
from anchore.util import contexts

# network operations

def get_feed_list():
    feedurl = contexts['anchore_config']['feeds_url']
    baseurl = feedurl
    url = baseurl
    timeout = 5

    ret = list()

    done = False
    while not done:
        record = anchore.anchore_auth.anchore_auth_get(contexts['anchore_auth'], url)
        if record['success']:
            data = json.loads(record['text'])
            if data and 'feeds' in data:
                ret = ret + data['feeds']
                if 'next_token' in data and data['next_token']:
                    url = baseurl + "?next_token="+data['next_token']
                else:
                    done=True
            else:
                done=True
        else:
            done=True
    return(ret)

def get_group_list(feed):
    feedurl = contexts['anchore_config']['feeds_url']
    baseurl = '/'.join([feedurl, feed])
    url = baseurl
    timeout = 5

    ret = list()

    done = False
    while not done:
        record = anchore.anchore_auth.anchore_auth_get(contexts['anchore_auth'], url)
        if record['success']:
            data = json.loads(record['text'])
            ret = ret + data['groups']
            if 'next_token' in data and data['next_token']:
                url = baseurl + "?next_token="+data['next_token']
            else:
                done=True
        else:
            done=True
    return(ret)
    

def get_group_data(feed, group, since="1970-01-01"):    
    feedurl = contexts['anchore_config']['feeds_url']
    baseurl = '/'.join([feedurl, feed, group, "?since="+since])
    url = baseurl
    timeout = 5

    updatetime = int(time.time())

    ret = list()
    last_token = ""
    done=False
    while not done:
        print "URL: " + url
        record = anchore.anchore_auth.anchore_auth_get(contexts['anchore_auth'], url, timeout=60)
        if record['success']:
            data = json.loads(record['text'])
            for d in data['data']:
                ret = ret + d

            if 'next_token' in data and data['next_token']:
                url = baseurl + "&next_token="+data['next_token']
                print "NEXT: " + url
                if last_token == data['next_token']:
                    done=True
                last_token = data['next_token']
            else:
                done=True
        else:
            done=True
    return(ret)


def sync_feedmeta():
    basedir = contexts['anchore_config']['feeds_dir']
    feedurl = contexts['anchore_config']['feeds_url']
    try:
        if not os.path.exists(basedir):
            os.makedirs(basedir)

        feeds = get_feed_list()
        if feeds:
            with open(os.path.join(basedir, "feeds.json"), 'w') as OFH:
                OFH.write(json.dumps(feeds))

            for feedrecord in feeds:
                feed = feedrecord['name']
                feeddir = os.path.join(basedir, feed)
                if not os.path.exists(feeddir):
                    os.makedirs(feeddir)

                groups = get_group_list(feed)
                if groups:
                    with open(os.path.join(feeddir, "groups.json"), 'w') as OFH:
                        OFH.write(json.dumps(groups))

                    for grouprecord in groups:
                        group = grouprecord['name']
                        groupdir = os.path.join(feeddir, group)
                        if not os.path.exists(groupdir):
                            os.makedirs(groupdir)
                else:
                    print "WARN: cannot get list of groups from feed: " + str(feed)
        else:
            print "ERROR: cannot get list of feeds"
            return(False)
    except Exception as err:
        import traceback
        traceback.print_exc()
        print "ERROR: " + str(err)
        return(False)

    return(True)

def sync_feeds():
    feedmeta = load_anchore_feedmeta()
    
    basedir = contexts['anchore_config']['feeds_dir']
    feedurl = contexts['anchore_config']['feeds_url']
    try:
        for feed in feedmeta.keys():
            if feedmeta[feed]['subscribed']:
                print "Subscribed to feed ("+str(feed)+"): syncing..."
                feeddir = os.path.join(basedir, feed)
                groups = feedmeta[feed]['groups'].keys()
                if groups:
                    for group in groups:
                        groupdir = os.path.join(feeddir, group)
                        if not os.path.exists(groupdir):
                            os.makedirs(groupdir)

                        sincets = 0
                        group_meta = {}
                        metafile = os.path.join(groupdir, "group_meta.json")
                        if os.path.exists(metafile):
                            with open(metafile, 'r') as FH:
                                group_meta.update(json.loads(FH.read()))
                                sincets = group_meta['last_update']

                        if 'files' not in group_meta:
                            group_meta['datafiles'] = list()

                        updatetime = int(time.time())

                        since=time.strftime("%Y-%m-%d", time.gmtime(sincets))
                        now = time.strftime("%Y-%m-%d", time.gmtime(updatetime))
                        print "SINCE: " + since
                        print "NOW: " + now
                        print "HERE: " + feed + " : " + group
                        if since != now:
                            datafilename = "data_"+since+"_to_"+now+".json"
                            datafile = os.path.join(groupdir, datafilename)
                            if os.path.exists(datafile):
                                pass
                                    #print "data already exists for this timeframe, skipping update"
                            else:
                                data = get_group_data(feed, group, since=since)
                                if data:
                                    with open(datafile, 'w') as OFH:
                                        OFH.write(json.dumps(data))

                                    with open(metafile, 'w') as OFH:
                                        group_meta['prev_update'] = sincets
                                        group_meta['last_update'] = updatetime
                                        group_meta['datafiles'].append(datafilename)
                                        OFH.write(json.dumps(group_meta))
                        else:
                            pass
                                #print "since and now are the same, skipping update"
    except Exception as err:
        print "ERROR: " + str(err)
        return(False)

    return(True)

# on disk data operations

def load_anchore_feeds_list():
    basedir = contexts['anchore_config']['feeds_dir']
    ret = list()
    
    feedsfile = os.path.join(basedir, "feeds.json")
    if os.path.exists(feedsfile):
        with open(feedsfile, 'r') as FH:
            ret = json.loads(FH.read())
    return(ret)

def load_anchore_feed_groups_list(feed):
    basedir = contexts['anchore_config']['feeds_dir']
    ret = list()
    feeddir = os.path.join(basedir, feed)
    
    fname = os.path.join(feeddir, "groups.json")
    if os.path.exists(fname):
        with open(fname, 'r') as FH:
            ret = json.loads(FH.read())
    return(ret)

def load_anchore_feed_group_datameta(feed, group):
    basedir = contexts['anchore_config']['feeds_dir']
    ret = {}
    
    groupdir = os.path.join(basedir, feed, group)
    
    fname = os.path.join(groupdir, "group_meta.json")
    if os.path.exists(fname):
        with open(fname, 'r') as FH:
            ret = json.loads(FH.read())
    return(ret)

def load_anchore_feedmeta():
    ret = {}

    basedir = contexts['anchore_config']['feeds_dir']
    feedfile = os.path.join(basedir, "feedmeta.json")
    feedmeta = {}
    if os.path.exists(feedfile):
        with open(feedfile, 'r') as FH:
            feedmeta = json.loads(FH.read())

    # ensure feed meta is up-to-date
    update_anchore_feedmeta(feedmeta)

    return(feedmeta)

def update_anchore_feedmeta(feedmeta):
    feeds = load_anchore_feeds_list()
    for feedrecord in feeds:
        feed = feedrecord['name']
        if feed not in feedmeta:
            feedmeta[feed] = {'subscribed':False, 'description':"NA", 'groups':{}}

        groups = load_anchore_feed_groups_list(feed)
        for grouprecord in groups:
            group = grouprecord['name']
            if group not in feedmeta[feed]['groups']:
                feedmeta[feed]['groups'][group] = {}

            datameta = load_anchore_feed_group_datameta(feed, group)
            if feedmeta[feed]['groups'][group] != datameta:
                feedmeta[feed]['groups'][group].update(datameta)
    save_anchore_feedmeta(feedmeta)
    return(True)

def save_anchore_feedmeta(feedmeta):
    basedir = contexts['anchore_config']['feeds_dir']
    feedfile = os.path.join(basedir, "feedmeta.json")
    if feedmeta:
        with open(feedfile, 'w') as OFH:
            OFH.write(json.dumps(feedmeta))
        return(True)
    return(False)

def subscribe_anchore_feed(feed):
    feedmeta = load_anchore_feedmeta()
    if feed in feedmeta and not feedmeta[feed]['subscribed']:
        feedmeta[feed]['subscribed'] = True
        save_anchore_feedmeta(feedmeta)
    return(True)

def unsubscribe_anchore_feed(feed):
    feedmeta = load_anchore_feedmeta()
    if feed in feedmeta and feedmeta[feed]['subscribed']:
        feedmeta[feed]['subscribed'] = False
        save_anchore_feedmeta(feedmeta)
    return(True)

def load_anchore_feed(feed, group):
    basedir = contexts['anchore_config']['feeds_dir']
    ret = {'success':False, 'msg':"", 'data':list()}
    datameta = {}

    feedmeta = load_anchore_feedmeta()
    if not feedmeta:
        ret['msg'] = "feed data does not exist: please sync feed data"
    elif feed in feedmeta and not feedmeta[feed]['subscribed']:
        ret['msg'] = "not currently subscribed to feed ("+str(feed)+"): please subscribe, sync, and try again"
    else:
        if feed in feedmeta and group in feedmeta[feed]['groups']:
            datameta = feedmeta[feed]['groups'][group]
            datadir = os.path.join(basedir, feed, group)
        
        if datameta and 'datafiles' in datameta:
            for datafile in datameta['datafiles']:
                thefile = os.path.join(datadir, datafile)
                with open(thefile, 'r') as FH:
                    thelist = json.loads(FH.read())
                ret['data'] = ret['data'] + thelist
                ret['success'] = True
                ret['msg'] = "success"
        else:
            ret['msg'] = "no data exists for given feed/group ("+str(feed)+"/"+str(group)+")"
            
    return(ret)
