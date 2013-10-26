# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import datetime
import time
import urllib.request
from bs4 import BeautifulSoup
import operator
import sqlite3
from PIL import Image, ImageFont, ImageDraw, ImageOps

def get_date(date_str):
    """
    Вытянуть дату
    //мне стыдно за такое решение
    """
    output = ""
    month = ('01','января'),('02','февраля'),('03','марта'),('04','апреля'),('05','мая'),('06','июня'),('07','июля'),('08','августа'),('09','сентября'),('10','октября'),('11','ноября'),('12','декабря')
    years = [2006,2007,2008,2009,2010,2011,2012]

    for mnum,month_str in month:
        if (date_str.find(month_str)>0):
            output += mnum + "_"
            break

    for year in years:
        if (date_str.find(str(year))>0):
            output += str(year)
            break
    else:
    #если нет года в списке значит это 2013
        output += '2013'
    return output


class Base:
    def __init__(self, dbname):
        self.con=sqlite3.connect(dbname)

    def __del__(self):
        self.con.close( )

    def maketables(self):
        """
        Для создания таблицы
        """
        self.con.execute('create table post(pid)')
        self.con.execute('create table post_tags(pid,tid,date)')
        self.con.execute('create table tags(tag_title)')
        #Сразу добавлю метки для постов которые закрыты или 404.
        self.add_tag(0,"parse_access_denied","")
        self.add_tag(0,"parse_error_404","")
        self.con.commit( )

    def get_tag(self, name, added = True):
        """
        Поиск тега, если есть вернуть tid, иначе создать новый
        cur - текущий тег
        res - будет получен если тег уже в базе
        added - Флаг/ если установлен то будет дописывать, если нет то возвращать false
        """
        cur=self.con.execute("select rowid from %s where %s='%s'" % ('tags','tag_title',name))
        res=cur.fetchone( )
        if res==None:
            if added:
                cur=self.con.execute("insert into %s (%s) values ('%s')" % ('tags','tag_title',name))
                self.con.commit( )
                return cur.lastrowid
            else:
                return False
        else:
            return res[0]

    def get_tag_name(self, id):
        cur=self.con.execute("select tag_title from %s where %s=%d" % ('tags','rowid',id))
        res=cur.fetchone( )
        return res[0]

    def add_tag(self, pid, name, date):
        """
        Добавление нового тега
        pid - ид поста
        name - сам тег
        date - дата поста
        """
        rowid = self.get_tag(name);
        print(pid,rowid ,name, date)
        self.con.execute("insert into %s (%s,%s,%s) values (%d,%d,'%s')" % ('post_tags','pid','tid','date',pid,rowid,date))
        self.con.commit( )

    def get_post(self, pid):
        """
        Получение поста если он есть в таблице post, иначе его добавление туда
        Просто ведение счёта просмотренных постов,
        будет полезно для запуска сразу нескольких скриптов параллельно
        """
        res=self.con.execute("select pid from %s where %s='%s'" % ('post','pid',pid)).fetchone( )
        if res==None:
            self.con.execute("insert into %s (%s) values ('%s')" % ('post','pid',pid))
            self.con.commit( )
            return False
        else:
            return True

    def add_post(self, pid):
        """
        Просмотр поста (выборка даты и тегов)
        """
        if (self.get_post(pid)):
            return

        print('-'*10,'http://habrahabr.ru/post/'+str(pid),'-'*10)
        cur=self.con.execute("select pid from %s where %s=%d" % ('post_tags','pid',pid))
        res=cur.fetchone( )
        if res==None:
            try:
                soup=BeautifulSoup(urllib.request.urlopen('http://habrahabr.ru/post/'+str(pid)).read( ))
            except (urllib.request.HTTPError):
                self.add_tag(pid,"parse_error_404","")
                print("error 404")
            else:
                published = soup.find("div", { "class" : "published" })
                tags = soup.find("ul", { "class" : "tags" })
                if tags:
                    for tag in tags.findAll("a"):
                        self.add_tag(pid, tag.string, get_date(published.string))
                else:
                    self.add_tag(pid,"parse_access_denied","")
                    print("access denied")
        else:
            print("post has already")

    def get_count_byname(self, name, date = ''):
        """
        Найти name по tid и получить количество по имени из get_count_byid
        name - имя тега
        date - (*)дата Формат mm_yyyy
        """
        tid = self.get_tag(name, False)
        return self.get_count_byid(tid, date)

    def get_count_byid(self, tid, date = ''):
        """
        Вернуть количество за весь период или за указанную дату
        """
        if tid:
            if date:
                count=self.con.execute("select count(pid) from %s where %s=%d and %s='%s'" % ('post_tags','tid',tid,'date',date))
            else:
                count=self.con.execute("select count(pid) from %s where %s=%d" % ('post_tags','tid',tid))
            res=count.fetchone( )
            return res[0]
        else:
            return False

    def get_graph(self, name):
        """
        Формирование списка дата - количество
        """
        month = ('01','января'),('02','февраля'),('03','марта'),('04','апреля'),('05','мая'),('06','июня'),('07','июля'),('08','августа'),('09','сентября'),('10','октября'),('11','ноября'),('12','декабря')
        years = [2006,2007,2008,2009,2010,2011,2012,2013]

        graph = []
        for Y in years:
            for M,M_str in month:
                date = str(M)+'_'+str(Y)
                graph.append((date, self.get_count_byname(name, date)))
        return graph

    def get_image(self, name):
        """
        Построение графика
        m_x - масштаб по X
        m_y - масштаб по Y
        img_x - ширина рисунка
        img_y - высота рисунка
        """
        img_x = 960
        img_y = 600

        img=Image.new('RGB',(img_x,img_y),(255,255,255))
        draw=ImageDraw.Draw(img)

        graph = self.get_graph(name)
        max_y = max(graph,key=lambda item:item[1])[1]
        if max_y == 0:
            print('tag not found')
            return False
        m_x, m_y = int(img_x/(len(graph))), int(img_y/max_y)

        draw.text((10, 10), str(max_y), (0,0,0))
        draw.text((10, 20), name, (0,0,0))

        x,prev_y = 0,-1
        for x_str, y in graph:
            x += 1
            if (x%12 == 1): draw.text((x*m_x, img_y - 30), str(x_str[3:]),(0,0,0))
            if prev_y >= 0: draw.line(((x-1)*m_x, img_y-prev_y*m_y-1, x*m_x, img_y-y*m_y-1), fill=(255,0,0))
            prev_y = y

        img.save('graph.png','PNG')
        Image.open('graph.png').show()

    def get_all_tags_sorted(self, tags):
        """
        По убыванию
        """
        return sorted(tags, key=lambda tag:tag[2], reverse=True)

    def get_all_tag_count(self):
        count=self.con.execute("select count(rowid) from %s" % ('tags'))
        res=count.fetchone( )
        alltag_count = res[0]
        tags = []
        for tag_id in range(alltag_count-1):
            tags.append((tag_id+1,self.get_tag_name(tag_id+1),self.get_count_byid(tag_id+1)))
            print (tag_id+1,self.get_tag_name(tag_id+1),self.get_count_byid(tag_id+1))
        return tags

    def write_infile(self, tags, filename):
        """
        Записывать в filename из tags
        """
        with open(filename, 'w') as f:
            for tag_id,tag_name,tag_count in tags:
                f.write(str(tag_id)+' '+tag_name+' '+str(tag_count)+"\n")
                print(str(tag_id)+' '+tag_name+' '+str(tag_count)+"\n")

extend = Base('tags.db')
extend.get_image('ццц')
#tags = extend.get_all_tag_count()
#sorted_tags = extend.get_all_tags_sorted(tags)
#extend.write_infile(sorted_tags,'tags.txt')