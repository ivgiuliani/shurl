drop table if exists entries;
create table entries (
  slug text primary key,
  url text not null,
  timestamp datetime default CURRENT_TIMESTAMP
);