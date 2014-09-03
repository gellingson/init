# migration 20140828
#
# adds tags column to listings
# adds 3 new tables
#
# MIGRATION INSTRUCTIONS:
#
# Just run this. Code will add tags over time.

alter table listing add (tags varchar(2048));

# heh, indices! Forgot a bunch of them!
create index sourceidx on listing(source_type, source_id, local_id);
create index sourcetextidx on listing(source_textid);

# non_canonical_make: field lengths shrank, and we never
# actually created it formally anyway, so do so here
# (even though we may find it convenient to use sqldump)
# see schema.sql for more docs

create table non_canonical_make(
id                int unsigned not null auto_increment,
non_canonical_name  varchar(50),
canonical_name		varchar(50),
consume_words		varchar(100),
push_words			varchar(100),
primary key (id),
unique index (non_canonical_name),
index ncn(non_canonical_name));

# non_canonical_model - see schema.sql for more docs
create table non_canonical_model(
id   int unsigned not null auto_increment,
non_canonical_make_id int unsigned,
non_canonical_name  varchar(50),
canonical_name	varchar(50),
consume_words		varchar(100),
push_words			varchar(100),
primary key (id),
unique index (non_canonical_name),
foreign key (non_canonical_make_id) references non_canonical_make(id));

# concept_tag - see schema.sql for more docs
create table concept_tag(
id    int unsigned not null auto_increment,
tag   varchar(20) not null,
syn_of_tag_id int unsigned,
display_tag varchar(20),
primary key (id),
unique index (tag),
foreign key (syn_of_tag_id) references concept_tag(id));

# concept_implies -- see schema.sql for more docs
create table concept_implies(
id    int unsigned not null auto_increment,
has_tag_id    int unsigned not null,
implies_tag_id    int unsigned not null,
index rels(has_tag_id, implies_tag_id),
primary key (id),
foreign key (has_tag_id) references concept_tag(id),
foreign key (implies_tag_id) references concept_tag(id));
