.. 2>/dev/null
 names () 
 { 
 echo -e "\n exit;\n**Contributors (sorted by number of commits):**\n";
 git log --format='%aN:%aE' origin/master | grep -Ev "(anonymous:|FYG_.*_bot_ignore_me)" | sed 's/@users.github.com/@users.noreply.github.com/g' | awk 'BEGIN{FS=":"}{match ($1, /^(%)?(.*)/, n) ; ct[n[2]]+=1; if (n[1] ~ /%/ || e[n[2]] == "" ) { e[n[2]]=$2}}END{for (i in e) { n[i]=e[i];c[i]+=ct[i] }; for (a in e) print c[a]"\t* "a" <"n[a]">";}' | sort -n -r | cut -f 2-
 }
 quine () 
 { 
 { 
 echo ".. 2>/dev/null";
 declare -f names | sed -e 's/^[[:space:]]*/ /';
 declare -f quine | sed -e 's/^[[:space:]]*/ /';
 echo -e " quine\n";
 names;
 echo -e "\n*To update the contributors list just run this file with bash. Prefix a name with % in .mailmap to set a contact as preferred*"
 } > CONTRIBUTORS.rst;
 exit
 }
 quine


 exit;
**Contributors (sorted by number of commits):**

* Alberto Pianon <alberto@pianon.eu>
* Peter Moser <p.moser@noi.bz.it>
* Alex Complojer <alex@agon-e.com>
* Martin Rabanser <martin.rabanser@rmb.bz.it>
* Chris Mair <chris@1006.org>
* Luca Miotto <l.miotto@noi.bz.it>
* Rahul Mohan Geetha <rahulmohang@gmail.com>
* Patrick Bertolla <p.bertolla@noi.bz.it>
* Carlo Piana <carlo@piana.eu>

*To update the contributors list just run this file with bash. Prefix a name with % in .mailmap to set a contact as preferred*
