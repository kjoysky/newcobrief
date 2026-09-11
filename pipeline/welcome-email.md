# Buttondown welcome email (sent the moment someone confirms)

NOT IN USE YET. Buttondown only lets Standard-plan accounts customize the welcome email (the API
returned 403 "requires a Standard plan"; we are on Basic, $9/mo). Decided 2026-09-11: not worth the
upgrade for this alone. The welcome page (newcobrief.com/welcome/) and the overnight first issue
(first_issue.py) do the job. If the plan is ever upgraded, paste this into Settings -> Subscribing ->
Welcome email. The `{% for %}` block is Buttondown templating; it prints one site link per city tag.

## Subject

You're in. Your first NewCo Brief arrives overnight.

## Body

Thanks for confirming. You're on the list for NewCo Brief.

**Your first issue arrives overnight** with this week's list for your city, every entry in full, with a one-line note on each. After that it comes every Monday morning from brief@newcobrief.com. Monday's issue covers the whole week, so it will repeat some of tonight's. From then on, each Monday is new.

Don't want to wait? This week's entries are on the site now, the lead trade in full and the rest counted:
{% for tag in subscriber.tags %}
https://newcobrief.com/{{ tag }}/
{% endfor %}
A sample issue, so you know what to expect: https://newcobrief.com/sample/

Reply to this email, or to any issue, and it reaches Kristina directly.
