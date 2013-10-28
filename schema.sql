drop table if exists entries;
create table entries (
  slug text primary key,
  url text not null,
  click_count integer default 0,
  timestamp datetime default CURRENT_TIMESTAMP
);