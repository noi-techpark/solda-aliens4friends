
-- table that holds the tinfoilhat files

drop table if exists tinfoilhat;
create table tinfoilhat (
    id bigserial,
    insert_ts timestamp with time zone default now(),
    session text,
    fname text,
    data jsonb,
    primary key(id),
    unique (session, fname)
);

-- don't try to compress jsonb (not worth it, unless disks are very slow)

alter table tinfoilhat alter data set storage external;

-- TODO: index (if needed at all), views
