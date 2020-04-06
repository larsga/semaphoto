
-- Initial schema

create table photo (
  id varchar(20) primary key,
  title varchar(100) not null,
  description varchar(1000),
  time_taken varchar(19) not null, -- not all timestamps are really timestamps
  taken_at varchar(20) not null,
  taken_by varchar(20),
  taken_during varchar(20),
  hidden boolean not null
); -- FIXME: VIDEO!

create table depicted_in (
  photo varchar(20) not null,
  person varchar(20) not null
);

create table in_category (
  photo varchar(20) not null,
  category varchar(20) not null
);

create table person (
  id varchar(20) primary key,
  name varchar(100) not null,
  username varchar(20),
  password varchar(20),
  hidden boolean not null
);

create table place (
  id varchar(20) primary key,
  name varchar(100) not null,
  parent varchar(20),
  latitude float,
  longitude float,
  hidden boolean not null
);

create table event (
  id varchar(20) primary key,
  name varchar(100) not null,
  description varchar(1000),
  start_date varchar(10) not null,
  end_date varchar(10) not null,
  hidden boolean not null
);

create table category (
  id varchar(20) primary key,
  name varchar(100) not null,
  description varchar(1000),
  hidden boolean not null
);

CREATE TABLE comments (
    id SERIAL,
    photo character varying(13) NOT NULL,
    verified integer DEFAULT 0 NOT NULL,
    datetime timestamp without time zone NOT NULL,
    username character varying(15) NOT NULL,
    content character varying(4000) NOT NULL,
    email character varying(100),
    name character varying(100),
    url character varying(100)
);

CREATE TABLE photo_score (
    id SERIAL,
    photo character varying(20) NOT NULL,
    username character varying(20) NOT NULL,
    score integer NOT NULL,
    updated timestamp without time zone NOT NULL
);
