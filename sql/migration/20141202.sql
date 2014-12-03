# migration 20141202
#
# add profile table
#
# MIGRATION INSTRUCTIONS:
#
# Just run this. See important note below on timing!

create table profile(
id        int unsigned not null auto_increment,
user_id   int,
newsletter char(1),
primary key (id),
foreign key (user_id) references auth_user(id)
);

# prepop records for existing accounts or they will break
# note that we're assuming this is run promptly at the same time as the
# new code is enabled so we don't miss any or try to recreate any profiles
insert into profile(user_id) select id from auth_user;
