import random
import re
import string
from functools import wraps

import MySQLdb.cursors
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
from flask_mysqldb import MySQL

app = Flask(__name__)

# email configurations
mail_settings = {
    "MAIL_SERVER": 'smtp.gmail.com',
    "MAIL_PORT": 465,
    "MAIL_USE_TLS": False,
    "MAIL_USE_SSL": True,
    "MAIL_USERNAME": 'noreplywhiteboard001@gmail.com',
    "MAIL_PASSWORD": 'csc322spring',
    "MAIL_DEFAULT_SENDER": 'noreplywhiteboard001@gmail.com',
    "MAIL_SUPPRESS_SEND": False
}

# creates the mail feature
app.config.update(mail_settings)
mail = Mail(app)

# Change this to your secret key (can be anything, it's for extra protection)
app.secret_key = '111'

# Enter your database connection details below
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '111111'
app.config['MYSQL_DB'] = 'csc322_project'

# Intialize MySQL
mysql = MySQL(app)


def login_required(func):  # login required decorator

    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get('user_id'):
            return func(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrapper


def admin_login_required(func):  # admin login required decorator

    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get('user_id')
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT tb_profile.*, tb_user.user_id FROM tb_user INNER JOIN tb_profile ON'
                       ' tb_profile.user_id = tb_user.user_id WHERE tb_user.user_id = %s ', (user_id,))
        issuper = cursor.fetchone()
        if issuper and issuper['user_type'] == 'SuperUser':
            return func(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrapper


@app.route("/admin/", methods=['GET', 'POST'])
@admin_login_required
def listofAdminpages():
    return render_template('admin.html')


@app.route("/pending/", methods=['GET', 'POST'])  # admin adding or deleting accounts
@admin_login_required  # must be logged in as admin to access this page!
def admin():
    if request.method == 'POST':
        # add the account to the database
        if 'Approve' in request.form:
            # get data
            user_name = request.form['username']
            email = request.form['email']
            interest = request.form['interest']
            credential = request.form['credential']
            reference = request.form['reference']
            user_password = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(10)])
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            # check to see if account already exist by email or user_name
            cursor.execute('SELECT * FROM tb_user WHERE email = %s OR user_name = %s', (email, user_name))
            account = cursor.fetchone()
            # if it doesnt insert into db
            if not account:
                cursor.execute("INSERT INTO tb_user (user_name, user_password, email, credential, reference, interest)"
                               " VALUES (%s, %s, %s, %s,%s, %s)",
                               (user_name, user_password, email, credential, reference, interest))
                # send email depending if it is an appeal or first time application
                if request.form['message'] == "NONE":
                    welcome = user_name + " your Whiteboard application has been approved and your account has been" \
                                          " created. Your temporary password is " + user_password + ". Use" \
                                                                                                    " this link to reset your password : http://localhost:5000/reset_password"
                else:
                    welcome = user_name + " your Whiteboard appeal has been approved and your account has" \
                                          " been created. Your temporary password is " + user_password + " Use" \
                                                                                                         " this link to reset your password : http://localhost:5000/reset_password"
                msg = Message("Welcome to Whiteboard!", recipients=[email])
                msg.body = welcome
                mail.send(msg)
            # delete from applied
            cursor.execute("DELETE FROM tb_applied WHERE email = %s", (email,))
            mysql.connection.commit()

        # reject the account
        elif 'Reject' in request.form:
            username = request.form['username']
            email = request.form['email']

            # send email depending if it appeal or first time applications
            if request.form['message'] == "NONE":
                reject = username + " we are sorry to say, your Whiteboard application has not been approved." \
                                    " Click on this link in order to appeal: http://localhost:5000/appeal"
            else:
                reject = username + " We are sorry to say, your Whiteboard appeal has not been approved"
                # put them into the blacklist if it is an appeal
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("INSERT INTO tb_blacklist (email, lastlogin)" "VALUES (%s,%s)", (email, '0'))
                mysql.connection.commit()
            msg = Message("Thank you for applying", recipients=[email])
            msg.body = reject
            mail.send(msg)

            # delete from tb applied
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("DELETE FROM tb_applied WHERE email = %s", (email,))
            mysql.connection.commit()

    # load the admin page
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM tb_applied')
    # Fetch all post records and return result
    applied = cursor.fetchall()
    if applied:
        return render_template('pending.html', applied=applied)
    return render_template('pending.html')


# page where they can reset the password
@app.route('/reset_password', methods=['POST', 'GET'])
def reset_password():
    msg = ''
    if request.method == "POST":
        # get information
        email = request.form['email']
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # check to see if the account exists and the information is correct
        cursor.execute('SELECT * FROM tb_user WHERE email = %s and user_password = %s', (email, old_password))
        account = cursor.fetchone()
        if not account:
            msg = "Unable to reset password"
            return render_template('reset_password.html', msg=msg)
        # if the info is correct than change password and indicate they have changed their password
        else:
            msg = "Success!"
            cursor.execute('UPDATE tb_user SET user_password = %s, didtheychangepass = %s WHERE user_id = %s',
                           (new_password, '1', account['user_id']))
            mysql.connection.commit()
            return render_template('reset_password.html', msg=msg)
    return render_template('reset_password.html')


# appeal a rejection
@app.route("/appeal", methods=['GET', 'POST'])
def appeal():
    msg = ''
    if request.method == "POST":
        username = request.form['username']
        email = request.form['email']
        interest = request.form['interest']
        credential = request.form['credential']
        reference = request.form['reference']
        message = request.form['message']
        # check to see if the email is already in the db
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM tb_user WHERE email = %s OR user_name = %s', (email, username))
        account = cursor.fetchone()
        cursor.execute('SELECT * FROM tb_applied WHERE email = %s OR username = %s', (email, username))
        applied = cursor.fetchone()
        # if email is in the system they cannot appeal
        if account or applied:
            msg = "You are already in the system - please check your email for a message from Whiteboard" \
                  " or try a different username"
            return render_template("appeal.html", msg=msg)
        else:
            cursor.execute("INSERT INTO tb_applied (username, email, interest, credential, reference, message)"
                           " VALUES (%s, %s, %s, %s, %s, %s)",
                           (username, email, interest, credential, reference, message))
            mysql.connection.commit()
            msg = "Your appeal will be shortly reviewed"
            return render_template('appeal.html', msg=msg)
    return render_template('appeal.html')


# this will be the home page, only accessible for loggedin users
@app.route("/")  # home page
def home():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # join table post and table user to get post_title, post_content, post_time, user_id, user_name
    cursor.execute('SELECT tb_post.*, tb_user.user_name, tb_profile.user_type FROM tb_post INNER JOIN tb_user ON'
                   ' tb_post.user_id = tb_user.user_id INNER JOIN tb_profile ON tb_profile.user_id = tb_post.user_id'
                   ' order by -post_time')
    # Fetch all post records and return result
    post = cursor.fetchall()
    # count replied number for each post
    for i in range(len(post)):
        cursor.execute('SELECT COUNT(post_id) FROM tb_reply WHERE post_id =%s', [post[i]['post_id']])
        count = cursor.fetchone()
        post[i]['replied_num'] = count.get('COUNT(post_id)')
    # sorted by the replied number to determine which post has the most replies
    post = sorted(post, key=lambda post: (post['replied_num']), reverse=True)
    # flag general post, since we need to show the top 3 rated post, we add the flag at the 4th post
    if len(post) > 3:
        post[3]['flag'] = 1

    # find all ordinary users who scores > 25
    cursor.execute('SELECT * FROM tb_profile WHERE user_type = "Ordinary" AND user_scores > 25')
    ou_vip = cursor.fetchall()
    for i in range(len(ou_vip)):
        # update to be VIP
        cursor.execute('UPDATE tb_profile SET user_type = %s WHERE user_id = %s', ('VIP', ou_vip[i]['user_id']))
        mysql.connection.commit()
    # find all VIP who scores < 25
    cursor.execute('SELECT * FROM tb_profile WHERE user_type = "VIP" AND user_scores < 25')
    vip_ou = cursor.fetchall()
    for i in range(len(vip_ou)):
        # demote to be Ordinary user
        cursor.execute('UPDATE tb_profile SET user_type = %s WHERE user_id = %s', ('Ordinary', vip_ou[i]['user_id']))
        mysql.connection.commit()
    #kickout that has a negative repuation number 
    cursor.execute('SELECT * FROM tb_profile WHERE user_status = 1 and user_scores < 0')
    kick_out = cursor.fetchall()
    for i in range(len(kick_out)):
        cursor.execute('UPDATE tb_profile SET user_status = %s WHERE user_id = %s',
                            ('0', kick_out[i]['user_id'])) 
        #add to blacklist 
        cursor.execute('SELECT email FROM tb_user WHERE user_id = %s',((kick_out[i]['user_id']),))
        email = cursor.fetchone()
        cursor.execute("INSERT INTO tb_blacklist (email, lastlogin)" "VALUES (%s,%s)", (email['email'],'0'))
        mysql.connection.commit()
    # Select all ordinary user profiles and sort by scores
    cursor.execute('SELECT tb_user.*, tb_profile.user_type, tb_profile.user_scores FROM tb_user INNER JOIN tb_profile '
                   'ON tb_user.user_id = tb_profile.user_id WHERE tb_profile.user_type = "Ordinary" order by '
                   '-tb_profile.user_scores ')
    top_OU = cursor.fetchall()
    # if exist ordinary user profiles
    if top_OU:
        # if total ordinary users < 3, only show their profiles
        if len(top_OU) < 3:
            top_OU = top_OU[:len(top_OU)]
        # otherwise, show the top 3 rated ordinary users' profiles
        else:
            top_OU = top_OU[:3]
    # Select all super user profiles and sort by scores
    cursor.execute('SELECT tb_user.*, tb_profile.user_type, tb_profile.user_scores FROM tb_user INNER JOIN tb_profile '
                   'ON tb_user.user_id = tb_profile.user_id WHERE tb_profile.user_type = "VIP" order by '
                   '-tb_profile.user_scores ')
    top_VIP = cursor.fetchall()
    # if exist super user profiles
    if top_VIP:
        # if total super users < 3, only show their profiles
        if len(top_VIP) < 3:
            top_VIP = top_VIP[:len(top_VIP)]
        # otherwise, show the top 3 rated super users' profiles
        else:
            top_VIP = top_VIP[:3]

    if post:
        return render_template('index.html', post=post, top_VIP=top_VIP, top_OU=top_OU)

    return render_template('index.html', top_VIP=top_VIP, top_OU=top_OU)


#  link the post_content to the reply page
@app.route('/reply/<post_id>/')
@login_required
def into_reply(post_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT tb_post.*, tb_user.user_name FROM tb_post INNER JOIN tb_user ON'
                   ' tb_post.user_id = tb_user.user_id WHERE tb_post.post_id = %s', (post_id,))
    posted = cursor.fetchone()
    # join table reply and table user to get reply information
    cursor.execute('SELECT tb_reply.*, tb_user.user_name FROM tb_reply INNER JOIN tb_user ON '
                   'tb_user.user_id = tb_reply.user_id WHERE tb_reply.post_id = %s order by -reply_time', (post_id,))
    reply = cursor.fetchall()
    # declare the reply_number
    reply_number = len(reply)
    session['post_id'] = posted['post_id']
    return render_template('reply.html', posted=posted, reply=reply, reply_number=reply_number)


# reply feature
@app.route('/add_reply/', methods=['post'])
def add_reply():
    if request.method == 'POST':
        reply_content = request.form['reply_content']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Find the current user information
        cursor.execute('SELECT * FROM tb_profile WHERE tb_profile.user_id = %s', [session['user_id']], )
        user_info = cursor.fetchone()
        # if the user_type is Ordinary
        if user_info['user_type'] == 'Ordinary':
            # Check out the taboo word list
            cursor.execute('SELECT * FROM tb_taboo')
            taboo_list = cursor.fetchall()
            # Create a list to save all taboo words the user typed in the post
            taboo_words = []
            for i in range(len(taboo_list)):
                # find all taboo words in the user post_content, ignore all cases
                taboo = re.findall(taboo_list[i]['word'], reply_content, flags=re.IGNORECASE)
                # if exist
                if taboo:
                    # remove repeat taboo words
                    taboo = list(dict.fromkeys(taboo))
                    # add into the list
                    taboo_words += taboo
                    for j in range(len(taboo)):
                        # replace the taboo words to be ***
                        reply_content = reply_content.replace(taboo[j], '***')
            # make all taboo words to be lower case
            taboo_words = [x.lower() for x in taboo_words]
            # remove the repeat taboo words
            taboo_words = list(dict.fromkeys(taboo_words))
            # if taboo_words exist:
            if taboo_words:
                cursor.execute('UPDATE tb_profile SET user_scores = %s WHERE user_id = %s',
                               ((user_info['user_scores'] - 1), session['user_id']))
                mysql.connection.commit()
                flash('Warning! Your Chat contains taboo words, Your Reputation will be reduced by this Rule:'
                      ' First Time use this word : -1 point, Next Time: -5 points ')

                for i in range(len(taboo_words)):
                    # insert taboo words into table user_taboo
                    cursor.execute('INSERT INTO tb_user_taboo (user_id, word) VALUES (%s, %s)',
                                   (session['user_id'], taboo_words[i]))
                    mysql.connection.commit()

                    # find all information of this user in table user_taboo
                    cursor.execute('SELECT * FROM tb_user_taboo WHERE user_id = %s AND word = %s',
                                   (session['user_id'], taboo_words[i]))
                    user_taboo = cursor.fetchall()
                    print(user_taboo)
                    # if this word occurs > 1, scores - 5
                    if len(user_taboo) > 1:
                        cursor.execute('UPDATE tb_profile SET user_scores = %s WHERE user_id = %s',
                                       ((user_info['user_scores'] - 5), session['user_id']))
                        mysql.connection.commit()

        # insert data into table reply: user_id, reply_content, post_id
        cursor.execute('INSERT INTO tb_reply (user_id, reply_content, post_id) VALUES '
                       '(%s, %s, %s)', (session['user_id'], reply_content, session['post_id']))
        mysql.connection.commit()
        return redirect(url_for('into_reply', post_id=session['post_id']))


@app.route('/login/', methods=['GET', 'POST'])
def login():
    # Output message if something goes wrong...
    msg = ''
    # Check if "email" and "password" POST requests exist (user submitted form)
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        # Create variables for easy access
        email = request.form['email']
        password = request.form['password']
        # Check if account exists using MySQL
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM tb_user WHERE email = %s AND user_password = %s', (email, password))
        # Fetch one record and return result
        account = cursor.fetchone()
        # If account exists in accounts table in out database
        if account:
            # check if in blacklist
            cursor.execute('SELECT * FROM tb_blacklist WHERE email = %s', (email,))
            blacklist = cursor.fetchone()
            if not blacklist or blacklist['lastlogin'] == 1:
                if blacklist:
                    cursor.execute("UPDATE tb_blacklist SET lastlogin = %s WHERE email= %s", ('0', email))
                    mysql.connection.commit()
                # Create session data, we can access this data in other routes
                session['loggedin'] = True
                session['user_id'] = account['user_id']
                session['username'] = account['user_name']
                # check if user is a new user
                cursor.execute('SELECT * FROM tb_profile WHERE user_id = %s', [session['user_id']])
                # if user is not a new user
                user_exist = cursor.fetchone()
                if user_exist:
                    # go profile page
                    if account['didtheychangepass'] == 0:
                        return redirect(url_for("reset_password"))
                    else:
                        return redirect(url_for('profile'))
                # get their score
                cursor.execute('SELECT user_id FROM tb_user WHERE user_name = %s', ([account['reference']],))
                exist = cursor.fetchone()
                if exist:
                    cursor.execute('SELECT user_type FROM tb_profile WHERE user_id = %s', (exist['user_id'],))
                    user = cursor.fetchone()
                    if user['user_type'] == 'Ordinary':
                        cursor.execute('INSERT INTO tb_profile (user_id, user_scores) VALUES (%s,%s)',
                                       ([session['user_id']], '10'))
                        mysql.connection.commit()
                    else:
                        cursor.execute('INSERT INTO tb_profile (user_id, user_scores) VALUES (%s,%s)',
                                       ([session['user_id']], '20'))
                        mysql.connection.commit()
                else:
                    # otherwise insert data into table profile: user_id, user_type, user_status, user_scores
                    cursor.execute('INSERT INTO tb_profile (user_id) VALUES (%s)', [session['user_id']])
                    mysql.connection.commit()
                # go profile page
                if account['didtheychangepass'] == 0:
                    return redirect(url_for("reset_password"))
                else:
                    return redirect(url_for('profile'))
        else:
            # Account doesnt exist or username/password incorrect
            msg = 'Incorrect email/password!'
    # Show the login form with message (if any)
    return render_template('login.html', msg=msg)


# this will be the registration page, we need to use both GET and POST requests
@app.route('/register/', methods=['GET', 'POST'])
def register():
    # Output message if something goes wrong...
    msg = ''
    # Check if "username", "password" and other text fields POST requests exist (user submitted form)
    if request.method == 'POST' and 'username' in request.form and \
            'email' in request.form and 'interest' in request.form and 'credential' in request.form and 'reference' in request.form:
        # Create variables for easy access
        username = request.form['username']  # get data from url
        email = request.form['email']
        interest = request.form['interest']
        credential = request.form['credential']
        reference = request.form['reference']

        # Check if account exists using MySQL
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM tb_user WHERE email = %s OR user_name = %s', (email, username))
        account = cursor.fetchone()
        cursor.execute('SELECT * FROM tb_applied WHERE email = %s OR username = %s', (email, username))
        application = cursor.fetchone()
        cursor.execute('SELECT * FROM tb_blacklist WHERE email = %s', (email,))
        blacklist = cursor.fetchone()
        # If account doesnt exists show error and validation checks
        if account or application or blacklist:
            msg = 'Invalid Email or Username!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address!'
        elif not re.match(r'[A-Za-z]+', username):
            msg = 'Username must contain only characters!'
        elif not re.match(r'[A-Za-z]+', interest):
            msg = 'Interest must contain only characters!'
        elif not re.match(r'[A-Za-z]+', credential):
            msg = 'Credential must contain only characters!'
        elif not re.match(r'[A-Za-z]+', reference):
            msg = 'Reference must contain only characters!'
        elif not username or not email or not credential or not reference or not interest:
            msg = 'Please fill out the form!'
        else:
            # Account doesnt exists and the form data is valid, now insert new account into applied table
            cursor.execute("INSERT INTO tb_applied (username, email, interest, credential, reference)"
                           " VALUES (%s, %s, %s, %s, %s)", (username, email, interest, credential, reference))
            mysql.connection.commit()
            msg = 'You have successfully applied! Look for an email containing your username and password'
            return render_template('login.html', msg=msg)
    elif request.method == 'POST':
        # Form is empty... (no POST data)
        msg = 'Please fill out the form!'
        # Show registration form with message (if any)
    return render_template('register.html', msg=msg)


# display current user on navigation bar
@app.context_processor
def my_context_processor():
    user_id = session.get('user_id')
    if user_id:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM tb_user WHERE user_id = %s', (user_id,))
        # Fetch one record and return result
        account = cursor.fetchone()
        if account:
            return {'account': account}
    return {}


# this will be the profile page, only accessible for loggedin users
@app.route('/profile/myProfile', methods=['POST', 'GET'])
def profile():
    # Check if user is loggedin
    if 'loggedin' in session:
        if request.method == "POST":

            # is user approved a group invitations
            if 'Approve' in request.form:
                group_id = request.form['group_id']
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                # insert them into the group, insert a message into the group chat, and delete the group from invites
                cursor.execute('INSERT INTO tb_group_members (group_id, user_name, user_id) VALUES (%s, %s, %s)',
                               (group_id, [session['username']], [session['user_id']],))
                cursor.execute('INSERT INTO tb_chat (user_id, group_id, chat_content) VALUES (%s, %s, %s)',
                               ([session['user_id']], group_id, "Has joined the group!"))
                cursor.execute('DELETE from tb_invite WHERE user_id = %s AND group_id = %s',
                               ([session['user_id']], group_id))
                mysql.connection.commit()

            # if user reject an invite
            elif 'Reject' in request.form:
                rejection = request.form['rejection']
                message = "Thank you for the consideration, but I will not accept invitation to this group." \
                          " I cannot join this group, " + rejection
                group_id = request.form['group_id']
                # insert the rejection message into group chat and delete the invitation
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute('INSERT INTO tb_chat (user_id, group_id, chat_content) VALUES (%s, %s, %s)',
                               ([session['user_id']], group_id, message))
                cursor.execute('DELETE from tb_invite WHERE user_id = %s AND group_id = %s',
                               ([session['user_id']], group_id))
                mysql.connection.commit()

            # if user is adding a user to their whitelist
            elif "whitelist" in request.form:
                user_whitelist = request.form['user_whitelist']
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                # check the user name the user inputted if exist in user database
                cursor.execute('SELECT user_name FROM tb_user WHERE user_name = %s', (user_whitelist,))
                user_name_exist = cursor.fetchone()
                # if not exist, output error message, then return to the group page
                if not user_name_exist:
                    flash("User doesn't exist")
                else:
                    # else check if the user is already in their whitelist or blacklist
                    cursor.execute('SELECT * FROM tb_whitelist WHERE user_id = %s AND user_name_friend = %s',
                                   ([session['user_id']], user_whitelist))
                    exist = cursor.fetchone()
                    cursor.execute('SELECT * FROM tb_user_blacklist WHERE user_id = %s AND user_name_blocked = %s',
                                   ([session['user_id']], user_whitelist))
                    otherlist = cursor.fetchone()
                    # if not then insert it into the correct list
                    if not exist and not otherlist:
                        cursor.execute("INSERT INTO tb_whitelist (user_id, user_name_friend)" "VALUES (%s,%s)",
                                       ([session['user_id']], user_name_exist['user_name']))
                        mysql.connection.commit()

            # user adding into the black list
            elif "blacklist" in request.form:
                user_blacklist = request.form['user_blacklist']
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                # check the user name the user inputted if exist in user database
                cursor.execute('SELECT user_name FROM tb_user WHERE user_name = %s', (user_blacklist,))
                user_name_exist = cursor.fetchone()
                # if not exist, output error message, then return to the group page
                if not user_name_exist:
                    flash("User doesn't exist")
                else:
                    # check if the user already exist in either of list
                    cursor.execute('SELECT * FROM tb_user_blacklist WHERE user_id = %s AND user_name_blocked = %s',
                                   ([session['user_id']], user_blacklist))
                    exist = cursor.fetchone()
                    cursor.execute('SELECT * FROM tb_whitelist WHERE user_id = %s AND user_name_friend = %s',
                                   ([session['user_id']], user_blacklist))
                    otherlist = cursor.fetchone()
                    # if not put them into the list
                    if not exist and not otherlist:
                        cursor.execute("INSERT INTO tb_user_blacklist (user_id, user_name_blocked)" "VALUES (%s,%s)",
                                       ([session['user_id']], user_name_exist['user_name']))
                        mysql.connection.commit()

        # We need all the account info for the user so we can display it on the profile page
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # ==============================EVALUATION SCORES===================================
        # get group_id where user evals are still pending
        cursor.execute('SELECT group_id FROM tb_user_evaluations WHERE user_id = %s AND evaluation_status = %s',
                       (session.get('user_id'), 'pending',))
        user_evaluation_group_id = cursor.fetchall()
        print(user_evaluation_group_id)

        # if user evaluations exists where
        if user_evaluation_group_id:
            print('Pending Evaluation for User obtained: ', user_evaluation_group_id)

            for i in range(0, len(user_evaluation_group_id)):

                # get total group members to complete close group form and find median of evaluated scores
                cursor.execute('SELECT user_id FROM tb_group_members WHERE group_id = %s ',
                               (user_evaluation_group_id[i]['group_id'],))
                total_group_members = cursor.fetchall()
                print('Total Group Members to Close Group and Evaluate User Scores: ', total_group_members)

                # check if total group members exist in tb_user_evaluation - that means user_eval scores are ready to be averaged into specific user in the group
                cursor.execute(
                    'SELECT rater_id from tb_user_evaluations where group_id = %s and evaluation_status = %s group by rater_id',
                    (user_evaluation_group_id[i]['group_id'], 'pending',))
                evaluated_group_members = cursor.fetchall()
                print('Users who have evaluated other users in group: ', evaluated_group_members)

                if len(total_group_members) == len(evaluated_group_members):
                    print('All users have evaluated! Get the median of your evaluated scores!')

                    # get all evaluation scores from user's group mates
                    cursor.execute(
                        'SELECT evaluation_score FROM tb_user_evaluations WHERE user_id = %s AND evaluation_status = %s',
                        (session['user_id'], 'pending',))
                    all_evaluation_scores = cursor.fetchall()
                    print(all_evaluation_scores)

                    # check if user already has score evaluated
                    cursor.execute('SELECT * from tb_user_evaluation_status WHERE user_id = %s AND group_id = %s',
                                   (session['user_id'], user_evaluation_group_id[i]['group_id'],))
                    already_added = cursor.fetchone()
                    print('-----------already adddeddddd-------')
                    print(already_added)
                    if already_added:
                        print('User already has evaluation score reflected in their reputation score!')
                    else:
                        total_score = 0

                        # take median of all scores and update value to user reputation score
                        for j in range(0, len(all_evaluation_scores)):
                            total_score += all_evaluation_scores[j]['evaluation_score']

                            # print('Users total score: ', total_score)
                            user_score = round(total_score / len(all_evaluation_scores))
                            print('Median User Evaluations:', user_score)

                            # update new rep score to user
                            cursor.execute('UPDATE tb_profile SET user_scores = user_scores + %s WHERE user_id = %s',
                                           (user_score, session['user_id']))

                            # insert eval_status for user in tb_user_evaluation_status
                            cursor.execute('INSERT INTO tb_user_evaluation_status (group_id, user_id) VALUES (%s, %s)',
                                           (user_evaluation_group_id[i]['group_id'], session['user_id'],))

                    user_score_added = 0

                    # if total_group_members in tb_user_evaluation_status - set evaluation_status to 'complete'
                    for k in range(0, len(total_group_members)):
                        cursor.execute('SELECT * from tb_user_evaluation_status WHERE user_id = %s',
                                       (total_group_members[k]['user_id'],))
                        score_added = cursor.fetchone()
                        if not score_added:
                            print('Not all user has had their scores added to their reputation score')
                        else:
                            user_score_added += 1

                    if user_score_added == len(total_group_members):
                        # if all user scores are added to their profile
                        # set all evaluation to 'evaluated'
                        cursor.execute('UPDATE tb_user_evaluations SET evaluation_status = %s WHERE group_id = %s',
                                       ('evaluated', user_evaluation_group_id[i]['group_id'],))

                    mysql.connection.commit()

                else:
                    print('Not All users have evaluated!')

        # join table profile and table user to get user information: id, name, email, user_type, user_scores,
        cursor.execute('SELECT tb_profile.*, tb_user.user_name, tb_user.email'
                       ' FROM tb_user INNER JOIN tb_profile ON tb_profile.user_id = tb_user.user_id'
                       ' WHERE tb_user.user_id = %s', [session['user_id']])
        account = cursor.fetchone()
        # get user post information
        cursor.execute('SELECT * FROM tb_post WHERE user_id = %s order by -post_time', [session['user_id']])
        # Fetch all records and return result
        post_history = cursor.fetchall()
        # get all the groups' information that the user is in
        cursor.execute('SELECT tb_group.*, tb_group_members.user_name FROM tb_group_members INNER JOIN tb_group'
                       ' ON tb_group.group_id = tb_group_members.group_id WHERE group_status = %s AND'
                       ' tb_group_members.user_name = %s',
                       ('active', [session['username']],))
        group_info = cursor.fetchall()

        # get all inactive groups that the user is in
        cursor.execute('SELECT tb_group.*, tb_group_members.user_name FROM tb_group_members INNER JOIN tb_group'
                       ' ON tb_group.group_id = tb_group_members.group_id WHERE group_status = %s AND'
                       ' tb_group_members.user_name = %s', ('inactive', [session['username']]), )
        inactive_groups = cursor.fetchall()
        print('All user inactive groups: ', inactive_groups)

        # have to join with the group tablle
        cursor.execute('SELECT tb_invite.*, tb_group.group_name, tb_group.group_describe FROM tb_group INNER JOIN '
                       'tb_invite ON tb_invite.group_id = tb_group.group_id WHERE tb_invite.user_id = %s',
                       [session['user_id']])
        invitation = cursor.fetchall()
        # get black and whitelist informations
        cursor.execute('SELECT user_name_friend FROM tb_whitelist WHERE user_id = %s', [session['user_id']])
        friends = cursor.fetchall()
        cursor.execute('SELECT user_name_blocked FROM tb_user_blacklist WHERE user_id = %s', [session['user_id']])
        blocked = cursor.fetchall()
        # Show the profile page with account info

        # find all ordinary users who scores > 25
        cursor.execute('SELECT * FROM tb_profile WHERE user_type = "Ordinary" AND user_scores > 25')
        ou_vip = cursor.fetchall()
        for i in range(len(ou_vip)):
            # update to be VIP
            cursor.execute('UPDATE tb_profile SET user_type = %s WHERE user_id = %s', ('VIP', ou_vip[i]['user_id']))
            mysql.connection.commit()
        # find all VIP who scores < 25
        cursor.execute('SELECT * FROM tb_profile WHERE user_type = "VIP" AND user_scores < 25')
        vip_ou = cursor.fetchall()
        for i in range(len(vip_ou)):
            # demote to be Ordinary user
            cursor.execute('UPDATE tb_profile SET user_type = %s WHERE user_id = %s',
                           ('Ordinary', vip_ou[i]['user_id']))
            mysql.connection.commit()
        return render_template('profile.html', account=account, post_history=post_history, group_info=group_info,
                               invitation=invitation, friends=friends, blocked=blocked,
                               completed_projects=inactive_groups)
    # User is not loggedin redirect to login page
    return redirect(url_for('login'))


# this will be the poster_file page
@app.route('/poster_profile/<poster_id>', methods=['POST', 'GET'])
# @login_required
def poster_profile(poster_id):
    if request.method == "POST":
        compliment_content = request.form['content']
        compliment_sender = session.get('user_id')
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            "INSERT INTO tb_compliments (compliment_sender, compliment_content, compliment_getter)" "VALUES (%s,%s,%s)",
            (compliment_sender, compliment_content, poster_id))
        mysql.connection.commit()

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # join table user and table profile to get the poster information: id, name, email, user_type, user_scores
    cursor.execute('SELECT tb_profile.*, tb_user.user_name, tb_user.email, tb_user.user_id'
                   ' FROM tb_user INNER JOIN tb_profile ON'
                   ' tb_profile.user_id = tb_user.user_id WHERE tb_user.user_id = %s', (poster_id,))
    account = cursor.fetchone()
    if not account:
        flash("User doesn't exist")
        return redirect(url_for('home'))
    # if the user is the poster, it will into himself profile page directly
    elif account['user_id'] == session.get('user_id'):
        return redirect(url_for('profile'))
    # otherwise, it will into the this poster's profile page
    # get poster's post history information: id, title, author, content, post_time and order by desc
    cursor.execute('SELECT tb_post.*, tb_user.user_name FROM tb_post INNER JOIN tb_user ON'
                   ' tb_post.user_id = tb_user.user_id WHERE tb_post.user_id = % s order by -post_time', (poster_id,))
    post_history = cursor.fetchall()
    cursor.execute('SELECT tb_group.group_id, tb_group.group_name FROM tb_group_members INNER JOIN tb_group ON'
                   ' tb_group.group_id = tb_group_members.group_id INNER JOIN tb_user ON'
                   ' tb_group_members.user_name = tb_user.user_name WHERE tb_user.user_id = %s', (poster_id,))

    others_group_info = cursor.fetchall()
    # find all ordinary users who scores > 25
    cursor.execute('SELECT * FROM tb_profile WHERE user_type = "Ordinary" AND user_scores > 25')
    ou_vip = cursor.fetchall()
    for i in range(len(ou_vip)):
        # update to be VIP
        cursor.execute('UPDATE tb_profile SET user_type = %s WHERE user_id = %s', ('VIP', ou_vip[i]['user_id']))
        mysql.connection.commit()
    # find all VIP who scores < 25
    cursor.execute('SELECT * FROM tb_profile WHERE user_type = "VIP" AND user_scores < 25')
    vip_ou = cursor.fetchall()
    for i in range(len(vip_ou)):
        # demote to be Ordinary user
        cursor.execute('UPDATE tb_profile SET user_type = %s WHERE user_id = %s',
                       ('Ordinary', vip_ou[i]['user_id']))
        mysql.connection.commit()
    return render_template('profile.html', poster_account=account, post_history=post_history,
                           others_group_info=others_group_info)


# this will be the logout page
@app.route('/logout/')
def logout():
    # Remove session data, this will log the user out
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/post/', methods=['GET', 'POST'])
@login_required
def post():
    msg = ''
    # Check if "username", "password" and "email" POST requests exist (user submitted form)
    if request.method == 'POST' and 'title' in request.form and 'content' in request.form:
        # Create variables for easy access
        title = request.form['title']  # get data from url form
        content = request.form['content']
        # Check if account exists using MySQL
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM tb_post WHERE post_title = %s', (title,))
        title_exist = cursor.fetchone()
        # If account exists show error and validation checks
        if title_exist:
            msg = 'Error: Title already exists!\n'
        else:
            # Find the current user information
            cursor.execute('SELECT * FROM tb_profile WHERE tb_profile.user_id = %s', [session['user_id']], )
            user_info = cursor.fetchone()
            # if the user_type is Ordinary
            if user_info['user_type'] == 'Ordinary':
                # Check out the taboo word list
                cursor.execute('SELECT * FROM tb_taboo')
                taboo_list = cursor.fetchall()
                # Create a list to save all taboo words the user typed in the post
                taboo_words = []
                for i in range(len(taboo_list)):
                    # find all taboo words in the user post_content, ignore all cases
                    taboo = re.findall(taboo_list[i]['word'], content, flags=re.IGNORECASE)
                    # if exist
                    if taboo:
                        # remove repeat taboo words
                        taboo = list(dict.fromkeys(taboo))
                        # add into the list
                        taboo_words += taboo
                        for j in range(len(taboo)):
                            # replace the taboo words to be ***
                            content = content.replace(taboo[j], '***')
                # make all taboo words to be lower case
                taboo_words = [x.lower() for x in taboo_words]
                # remove the repeat taboo words
                taboo_words = list(dict.fromkeys(taboo_words))
                if taboo_words:
                    cursor.execute('UPDATE tb_profile SET user_scores = %s WHERE user_id = %s',
                                   ((user_info['user_scores'] - 1), session['user_id']))
                    mysql.connection.commit()
                    flash('Warning! Your Post contains taboo words, Your Reputation will be reduced by this Rule:'
                          ' First Time use this word : -1 point, Next Time: -5 points ')

                    for i in range(len(taboo_words)):
                        # insert taboo words into table user_taboo
                        cursor.execute('INSERT INTO tb_user_taboo (user_id, word) VALUES (%s, %s)',
                                       (session['user_id'], taboo_words[i]))
                        mysql.connection.commit()

                        # find all information of this user in table user_taboo
                        cursor.execute('SELECT * FROM tb_user_taboo WHERE user_id = %s AND word = %s',
                                       (session['user_id'], taboo_words[i]))
                        user_taboo = cursor.fetchall()
                        print(user_taboo)
                        # if this word occurs > 1, scores - 5
                        if len(user_taboo) > 1:
                            cursor.execute('UPDATE tb_profile SET user_scores = %s WHERE user_id = %s',
                                           ((user_info['user_scores'] - 5), session['user_id']))
                            mysql.connection.commit()

            # Account doesnt exists and the form data is valid, now insert new account into accounts table
            cursor.execute("INSERT INTO tb_post (post_title, post_content, user_id)"
                           " VALUES (%s, %s, %s)", (title, content, session['user_id']))
            mysql.connection.commit()
            return redirect(url_for('home'))

    elif request.method == 'POST':
        # Form is empty... (no POST data)
        msg = 'Please fill out the form!'
        # Show registration form with message (if any)
    return render_template('post.html', msg=msg)


# delete post
@app.route('/profile/myProfile/<post_id>/')
def delete_post(post_id):
    if request.method == 'GET':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('DELETE FROM tb_post WHERE post_id = %s', (post_id,))
        mysql.connection.commit()
        return redirect(url_for('profile'))


# search bar
@app.route('/search/', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == "POST" and 'username' in request.form:
        username = request.form['username']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # search by username
        cursor.execute('SELECT * FROM tb_user WHERE user_name = %s', (username,))
        account = cursor.fetchone()
        if not account:
            flash('User does not exist')
            return redirect(url_for('home'))
        # if user search himself, it will into his profile page directly
        elif account['user_name'] == session['username']:
            return redirect(url_for('profile'))
        else:
            # otherwise, go to the profile page of the searched user
            return redirect(url_for('poster_profile', poster_id=account['user_id']))


# create a group
@app.route('/group/', methods=['GET', 'POST'])
def create_group():
    if request.method == "POST":
        group_name = request.form['group_name']
        group_describe = request.form['describe']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # check if the group name entered by the user was in the table group
        cursor.execute('SELECT * FROM tb_group WHERE group_name = %s', (group_name,))
        group_name_exist = cursor.fetchone()
        # if exist: show the error message and return to the profile page
        if group_name_exist:
            flash('Group Already Exist')
            return redirect(url_for('profile'))
        # otherwise insert data into table group: group_name, user_id, group_describe
        cursor.execute('INSERT INTO tb_group (group_name, user_id, group_describe) VALUES (%s, %s, %s)',
                       (group_name, session['user_id'], group_describe))
        mysql.connection.commit()
        # get the group id by desc
        cursor.execute('SELECT group_id FROM tb_group order by -group_id')
        group_id = cursor.fetchone()

        # insert data into table group_members: group_id and user_name
        cursor.execute('INSERT INTO tb_group_members (group_id, user_name, user_id) VALUES (%s, %s, %s)',
                       (group_id['group_id'], session['username'], session['user_id']))
        mysql.connection.commit()
        return redirect(url_for('profile'))


# group page
@app.route("/into_group/<group_id>")
def into_group(group_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # get group status if active or inactive
    cursor.execute('SELECT group_status FROM tb_group WHERE group_id=%s', (group_id,))
    group_status = cursor.fetchone()
    group_status = group_status['group_status']

    # get the group's information: group_name, group_describe, group_id, group_created_time, group_creater if exist
    cursor.execute('SELECT tb_group.*, tb_group_members.user_name FROM tb_group_members INNER JOIN tb_group'
                   ' ON tb_group.group_id = tb_group_members.group_id WHERE tb_group.group_id = %s', (group_id,))

    group = cursor.fetchone()
    # get the group members' information: user_name, user_id
    cursor.execute('SELECT tb_group_members.*, tb_user.user_id FROM tb_group_members INNER JOIN tb_user '
                   'ON tb_group_members.user_name = tb_user.user_name WHERE'
                   ' tb_group_members.group_id = %s', (group_id,))
    group_members = cursor.fetchall()
    session['group_id'] = group_id
    cursor.execute('SELECT tb_chat.*, tb_user.user_name FROM tb_chat INNER JOIN tb_user ON'
                   ' tb_user.user_id = tb_chat.user_id WHERE tb_chat.group_id = %s', (group_id,))
    chat = cursor.fetchall()

    # for all group_member id in group, get user's praises and warnings
    # cursor.execute('SELECT user_praises, user_warnings from tb_group_members where')
    group_member_points = []
    for i in range(0, len(group_members)):
        cursor.execute(
            'SELECT user_id, user_praises, user_warnings from tb_group_members where user_id = %s and group_id = %s',
            (group_members[i]['user_id'], group_id,))
        member_points = cursor.fetchone()
        group_member_points.append(member_points)

    # replace all user_id with respective user_name into group_member_points
    for i in range(0, len(group_members)):
        cursor.execute('SELECT user_name from tb_user where user_id = %s', (group_members[i]['user_id'],))
        member_user_name = cursor.fetchone()
        group_member_points[i]['user_id'] = member_user_name

    # get all group polls if there exists any
    cursor.execute('SELECT * from tb_poll where group_id = %s', (group_id,))
    polls = cursor.fetchall()
    poll_id_data = []
    poll_ids = ''
    # grab all group poll ID
    for poll in polls:
        poll_id_data.append(poll['poll_id'])
        poll_ids += str(poll['poll_id']) + ','

    # concatenate poll.optionText together grouped by poll_id
    cursor.execute('select tb_group.group_id, tb_poll.poll_id,'
                   ' tb_poll.poll_title, tb_poll.poll_body, group_concat(optionText)'
                   ' from tb_group join tb_poll on tb_group.group_id = tb_poll.group_id join'
                   ' tb_poll_options on tb_poll.poll_id = tb_poll_options.poll_id'
                   ' where tb_poll.poll_id in (select poll_id from tb_poll where poll_id'
                   ' NOT IN (select poll_id from tb_poll_responses where tb_poll_responses.user_id = %s)'
                   ' and group_id = %s) group by poll_id', (session.get('user_id'), group_id,))
    all_options = cursor.fetchall()
    if all_options:
        # attempt to traverse through group_concat(optionText)
        for i in range(0, len(all_options)):
            # print(all_options[i]['group_concat(optionText)'])
            current_poll_option = all_options[i]['group_concat(optionText)'].split(',')
            all_options[i]['group_concat(optionText)'] = all_options[i]['group_concat(optionText)'].split(',')

    else:
        all_options = []

    # get user's voted polls information/data
    cursor.execute('select tb_poll.poll_title, tb_poll.poll_body, tb_poll.poll_id,'
                   ' tb_poll_options.optionText from tb_poll join tb_poll_options on'
                   ' tb_poll.poll_id = tb_poll_options.poll_id join tb_poll_responses'
                   ' on tb_poll_options.option_id = tb_poll_responses.option_id where'
                   ' tb_poll_responses.user_id = %s and tb_poll.group_id = %s', (session.get('user_id'), group_id,))
    voted_polls = cursor.fetchall()

    if voted_polls:
        for i, poll in enumerate(voted_polls):
            # get highest count option givn poll_id
            cursor.execute(
                'select option_id, COUNT(option_id)  from tb_poll_responses where poll_id = %s group by option_id order by count(option_id) desc limit 1',
                (poll['poll_id'],))
            poll_highest_vote_count = cursor.fetchone()

            # get poll_highest_vote_count's optionText
            cursor.execute('select optionText from tb_poll_options where option_id = %s',
                           (poll_highest_vote_count['option_id'],))
            highest_vote_option = cursor.fetchone()

            # traverse through voted_poll data and add poll_highest_vote_count into vote_count, and highest_vote_option into highest_vote
            voted_polls[i]['vote_count'] = poll_highest_vote_count['COUNT(option_id)']
            voted_polls[i]['highest_vote'] = highest_vote_option['optionText']

        # print('------------NEW ALTERED VOTED POLL DATA_----------------')
        # print(voted_polls)

        # =========================Group Vote=============================

    # get all unresponded user group votes

    cursor.execute('select group_vote_id, vote_subject, user_subject, user_id from tb_group_votes where'
                   ' (group_vote_id not in (select group_vote_id from tb_group_vote_responses'
                   ' where group_id = %s and voter_id = %s) and group_vote_status = %s and group_id = %s)',
                   (group_id, session.get('user_id'), 'open', group_id,))

    all_group_votes = cursor.fetchall()
    print('----------ALL UNRESPONDED GROUP VOTES---------')
    print(all_group_votes)

    user_subject_username = []
    # for all user_subject in group_votes get user_name
    for group_vote in all_group_votes:
        # print(group_vote['user_subject'])
        if group_vote['user_subject'] is not None:
            cursor.execute('SELECT user_name from tb_user where user_id = %s', (group_vote['user_subject'],))
            subject_username = cursor.fetchone()
            user_subject_username.append(subject_username['user_name'])

        else:
            user_subject_username.append(None)

    # add subject username into group_vote data
    for i in range(0, len(all_group_votes)):
        if all_group_votes[i]['user_subject'] is not None:
            all_group_votes[i]['user_subject'] = user_subject_username[i]
        else:
            continue

    # get user's responded group votes
    cursor.execute(
        'select tb_group_votes.group_id, tb_group_votes.group_vote_id, tb_group_vote_responses.vote_response, tb_group_votes.vote_subject, tb_group_votes.user_subject, tb_group_votes.group_vote_status, tb_group_votes.highest_vote, tb_group_votes.vote_count from tb_group_votes join tb_group_vote_responses on tb_group_votes.group_vote_id = tb_group_vote_responses.group_vote_id where tb_group_vote_responses.voter_id = %s and tb_group_votes.group_id = %s',
        (session.get('user_id'), group_id,))
    voted_group_votes = cursor.fetchall()

    # replace user_subject id with user_subject usernames
    subject_usernames = []
    # for all user_subject in group_votes get user_name
    for group_vote in voted_group_votes:
        if group_vote['user_subject'] is not None:
            cursor.execute('SELECT user_name from tb_user where user_id = %s', (group_vote['user_subject'],))
            subject_username = cursor.fetchone()
            subject_usernames.append(subject_username['user_name'])
        else:
            subject_usernames.append(None)

    # add subject username into group_vote data
    for i in range(0, len(voted_group_votes)):
        if voted_group_votes[i]['user_subject'] is not None:
            voted_group_votes[i]['user_subject'] = subject_usernames[i]
        else:
            continue

    # get highest vote count for each voted group_votes
    if voted_group_votes:
        for i, group_vote in enumerate(voted_group_votes):
            cursor.execute(
                'select group_id, group_vote_id, COUNT(vote_response), vote_response from tb_group_vote_responses where group_vote_id = %s group by vote_response order by COUNT(vote_response) desc limit 1',
                (group_vote['group_vote_id'],))
            highest_group_vote = cursor.fetchone()

            # store highest group vote count and highest vote response text into voted_group_votes
            voted_group_votes[i]['vote_count'] = highest_group_vote['COUNT(vote_response)']
            voted_group_votes[i]['highest_vote'] = highest_group_vote['vote_response']

    # check if all users have voted on USER_RELATED GROUP POLLS
    # get total number of group members in group
    cursor.execute('SELECT COUNT(group_id) from tb_group_members where group_id=%s', (group_id,))
    total_group_members = cursor.fetchone()
    total_group_members = total_group_members['COUNT(group_id)']
    vote_count_needed = total_group_members - 1

    # traverse through all voted_group_polls to see if there is a unanimous vote
    for i, group_vote in enumerate(voted_group_votes):
        cursor.execute(
            'SELECT COUNT(group_vote_id) from tb_group_vote_responses where group_id=%s and group_vote_id=%s',
            (group_id, group_vote['group_vote_id']))
        total_group_vote_responses = cursor.fetchone()

        if group_vote['user_subject'] is not None:
            cursor.execute('SELECT user_id FROM tb_user where user_name = %s', (group_vote['user_subject'],))
            user_id = cursor.fetchone()
            user_id = user_id['user_id']

            # if total_group_vote_responses['COUNT(group_vote_id)'] = vote_count_needed, DO THE VOTE SUBJECT!!!!
            # get highest_vote, user_subject, vote_subject
            if total_group_vote_responses['COUNT(group_vote_id)'] == vote_count_needed:
                if group_vote['highest_vote'] == 'Yes':
                    print(group_vote['user_subject'], ' will get a ', group_vote['vote_subject'])
                    if group_vote['vote_subject'] == 'praise' and group_vote['group_vote_status'] == 'open':
                        # update user praise points
                        cursor.execute(
                            'UPDATE tb_group_members SET user_praises = user_praises + 1 where user_id = %s and group_id=%s',
                            (user_id, group_id,))
                        cursor.execute('UPDATE tb_group_votes SET group_vote_status = %s WHERE group_vote_id = %s',
                                       ('closed', group_vote['group_vote_id']))
                        # save to db
                        mysql.connection.commit()
                        # auto reload
                    elif group_vote['vote_subject'] == 'warning' and group_vote['group_vote_status'] == 'open':
                        # check if user has >= 3 warnings
                        cursor.execute('SELECT user_warnings FROM tb_group_members WHERE group_id = %s AND user_id = %s', (group_id, user_id,))
                        user_warnings = cursor.fetchone()
                        print('-------USER WARNINGS--------')
                        print(user_warnings)

                        if user_warnings['user_warnings'] == 2:
                            # remove and deduct points to the user
                            cursor.execute('DELETE FROM tb_group_members WHERE user_id = %s AND group_id = %s',
                                           (user_id, group_id,))
                            # deduct 5 points to user
                            cursor.execute('UPDATE tb_profile SET user_scores = user_scores - 5 WHERE user_id = %s', (user_id,))

                            cursor.execute('UPDATE tb_group_votes SET group_vote_status = %s WHERE group_vote_id = %s',
                                           ('closed', group_vote['group_vote_id']))

                            mysql.connection.commit()
                        else:
                            cursor.execute(
                                'UPDATE tb_group_members SET user_warnings = user_warnings + 1 where user_id = %s',
                                (user_id,))
                            cursor.execute('UPDATE tb_group_votes SET group_vote_status = %s WHERE group_vote_id = %s',
                                           ('closed', group_vote['group_vote_id']))
                            mysql.connection.commit()
                        # else, user will get removed from the group
                    elif group_vote['vote_subject'] == 'user_removal' and group_vote['group_vote_status'] == 'open':
                        cursor.execute('DELETE FROM tb_group_members WHERE user_id = %s AND group_id = %s',
                                       (user_id, group_id,))
                        cursor.execute('UPDATE tb_profile SET user_scores = user_scores - 10 WHERE user_id = %s', (user_id,))
                        cursor.execute('UPDATE tb_group_votes SET group_vote_status = %s WHERE group_vote_id = %s',
                                       ('closed', group_vote['group_vote_id']))

                        mysql.connection.commit()
                    else:
                        print(group_vote['user_subject'], ' will not get a ', group_vote['vote_subject'])

        # else if group_vote['user_subject] is None = close_group
        else:
            # get COUNT(group_vote_id) where vote_subject = 'close_group'
            if total_group_vote_responses['COUNT(group_vote_id)'] == total_group_members:
                if group_vote['highest_vote'] == 'Yes':
                    print('The group will be closed!')

                    # check if all group_members have filled out close group eval form
                    num_of_evaluations = 0

                    for k in range(0, len(group_members)):
                        cursor.execute('SELECT * FROM tb_user_evaluations WHERE rater_id = %s AND group_id = %s',
                                       (group_members[k]['user_id'], group_id,))
                        user_evaluated = cursor.fetchone()

                        if user_evaluated:
                            num_of_evaluations = num_of_evaluations + 1

                    print('Close Group Eval Submissions: ', num_of_evaluations)
                    print('Total Number of Group Members: ', len(group_members))

                    # if every group_member has submitted eval form, CLOSE THE GROUP - set group_status to inactive!!!
                    if num_of_evaluations == len(group_members):
                        # set group_status to inactive!!!!
                        cursor.execute('UPDATE tb_group SET group_status = %s WHERE group_id = %s',
                                       ('inactive', group_id,))

                        mysql.connection.commit()

                        # return redirect(url_for('home'))
                        return render_template('group.html', group=group, group_members=group_members, chat=chat,
                                               voted_polls=voted_polls, polls=all_options, group_status=group_status,
                                               group_votes=all_group_votes, voted_group_votes=voted_group_votes,
                                               member_points=group_member_points)

                    # not all close group eval form submitted
                    elif num_of_evaluations < len(group_members):
                        # if check if user completed evaluation form: user_id is not in tb_user_evaluations - redirect to index: ultimately redirect to 'Thank you for evaluating'
                        cursor.execute('SELECT * from tb_user_evaluations WHERE rater_id = %s AND group_id= %s',
                                       (session['user_id'], group_id,))
                        evaluation_completed = cursor.fetchone()
                        if evaluation_completed:
                            return render_template('close_group.html', group_id=group_id,
                                                   completed=evaluation_completed)
                        else:
                            # redirect to close group evaluation form
                            return redirect(url_for('close_group', group_id=group_id, group_members=group_members))
                else:
                    print('The group will not be closed')
    mysql.connection.commit()

    # set flag not_in_group
    not_in_group = True
    # if the user is a visitor
    if not session.get('user_id'):
        # set flag = True
        not_in_group = True
    # check the user is a group member in this group or not
    else:
        cursor.execute('SELECT * FROM tb_group_members WHERE tb_group_members.user_name = %s AND '
                       'tb_group_members.group_id = %s', (session.get('username'), group_id))
        is_group_member = cursor.fetchone()
        # if the user is a group member in this group, go group page and show all information
        if is_group_member:
            return render_template('group.html', group=group, group_members=group_members, chat=chat,
                                   voted_polls=voted_polls, polls=all_options, group_status=group_status,
                                   group_votes=all_group_votes, voted_group_votes=voted_group_votes,
                                   member_points=group_member_points)
    # otherwise, only show some public information such as group members list, description....
    return render_template('group.html', group=group, group_members=group_members, chat=chat, voted_polls=voted_polls,
                           polls=all_options, not_in_group=not_in_group, group_status=group_status,
                           member_points=group_member_points)


# invite feature
@app.route("/invite/<group_id>", methods=['POST'])
def invite(group_id):
    if request.method == 'POST':
        user_name = request.form['user_name']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # check the user name the user inputted if exist in user database
        cursor.execute('SELECT user_name FROM tb_user WHERE user_name = %s', (user_name,))
        user_name_exist = cursor.fetchone()
        # if not exist, output error message, then return to the group page
        if not user_name_exist:
            flash("User doesn't exist")
            return redirect(url_for('into_group', group_id=group_id))
        # otherwise, check the username if exist in this group
        cursor.execute('SELECT tb_group_members.* FROM tb_group_members INNER JOIN tb_user ON '
                       'tb_group_members.user_name = tb_user.user_name'
                       ' WHERE tb_user.user_name = %s AND tb_group_members.group_id = %s', (user_name, group_id))
        group_member = cursor.fetchall()
        # if this user already in this group, show the error message
        if group_member:
            flash('This User Already in this Group')
            return redirect(url_for('into_group', group_id=group_id))
        # otherwise, see where to place the user by getting their username
        cursor.execute('SELECT user_id FROM tb_user WHERE user_name = %s', (user_name,))
        account = cursor.fetchone();
        where_to_place = 'invitation'

        # check to see if the adder is in the invitees white or black list
        cursor.execute("SELECT user_name_friend FROM tb_whitelist WHERE user_id = %s", ([account['user_id']],))
        friends = cursor.fetchall()
        cursor.execute("SELECT user_name_blocked FROM tb_user_blacklist WHERE user_id =%s", ([account['user_id']]))
        blocked = cursor.fetchall()
        for friend in friends:
            if friend['user_name_friend'] == session['username']:
                where_to_place = "whitelist"
        for block in blocked:
            if block['user_name_blocked'] == session['username']:
                where_to_place = 'blacklist'

        # added in in invitee whitelist automatically add into the group with a message
        if where_to_place == 'whitelist':
            cursor.execute('INSERT INTO tb_group_members (group_id, user_name, user_id) VALUES (%s, %s, %s)',
                           (group_id, user_name, account['user_id']))
            cursor.execute('INSERT INTO tb_chat (user_id, group_id, chat_content) VALUES (%s, %s, %s)',
                           ([account['user_id']], group_id, "Has joined the group!"))
            mysql.connection.commit()

        # adder is in the blacklist display automatic rejection message in group
        elif where_to_place == 'blacklist':
            cursor.execute('INSERT INTO tb_chat (user_id, group_id, chat_content) VALUES (%s, %s, %s)',
                           ([account['user_id']], group_id,
                            "Thank you for the consideration, but I will not accept invitation to this group."))
            mysql.connection.commit()

        # adder is in neither, send a invitation to the invitee's profile page
        else:
            cursor.execute("SELECT * FROM tb_invite WHERE user_id =%s AND group_id = %s",
                           (account['user_id'], group_id))
            invited = cursor.fetchone()
            # check to see if invitations already sent
            if invited:
                flash('This users is already invited')
            else:
                cursor.execute("INSERT INTO tb_invite (user_id,group_id)" " VALUES (%s,%s)",
                               (account['user_id'], group_id))
                mysql.connection.commit()
        return redirect(url_for('into_group', group_id=group_id))


@app.route('/into_group/<group_id>")', methods=['POST'])
@login_required
def chat(group_id):
    if request.method == 'POST':
        # Create variables for easy access
        chat_content = request.form['chat_content']
        # Check if account exists using MySQL
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Find the current user information
        cursor.execute('SELECT * FROM tb_profile WHERE tb_profile.user_id = %s', [session['user_id']], )
        user_info = cursor.fetchone()
        # if the user_type is Ordinary
        if user_info['user_type'] == 'Ordinary':
            # Check out the taboo word list
            cursor.execute('SELECT * FROM tb_taboo')
            taboo_list = cursor.fetchall()
            # Create a list to save all taboo words the user typed in the post
            taboo_words = []
            for i in range(len(taboo_list)):
                # find all taboo words in the user post_content, ignore all cases
                taboo = re.findall(taboo_list[i]['word'], chat_content, flags=re.IGNORECASE)
                # if exist
                if taboo:
                    # remove repeat taboo words
                    taboo = list(dict.fromkeys(taboo))
                    # add into the list
                    taboo_words += taboo
                    for j in range(len(taboo)):
                        # replace the taboo words to be ***
                        chat_content = chat_content.replace(taboo[j], '***')
            # make all taboo words to be lower case
            taboo_words = [x.lower() for x in taboo_words]
            # remove the repeat taboo words
            taboo_words = list(dict.fromkeys(taboo_words))
            # if taboo_words exist:
            if taboo_words:
                cursor.execute('UPDATE tb_profile SET user_scores = %s WHERE user_id = %s',
                               ((user_info['user_scores'] - 1), session['user_id']))
                mysql.connection.commit()
                flash('Warning! Your Chat contains taboo words, Your Reputation will be reduced by this Rule:'
                      ' First Time use this word : -1 point, Next Time: -5 points ')

                for i in range(len(taboo_words)):
                    # insert taboo words into table user_taboo
                    cursor.execute('INSERT INTO tb_user_taboo (user_id, word) VALUES (%s, %s)',
                                   (session['user_id'], taboo_words[i]))
                    mysql.connection.commit()

                    # find all information of this user in table user_taboo
                    cursor.execute('SELECT * FROM tb_user_taboo WHERE user_id = %s AND word = %s',
                                   (session['user_id'], taboo_words[i]))
                    user_taboo = cursor.fetchall()
                    print(user_taboo)
                    # if this word occurs > 1, scores - 5
                    if len(user_taboo) > 1:
                        cursor.execute('UPDATE tb_profile SET user_scores = %s WHERE user_id = %s',
                                       ((user_info['user_scores'] - 5), session['user_id']))
                        mysql.connection.commit()

        cursor.execute('INSERT INTO tb_chat (user_id, group_id, chat_content) VALUES (%s, %s, %s)',
                       (session['user_id'], group_id, chat_content))
        mysql.connection.commit()
        return redirect(url_for('into_group', group_id=group_id))


@app.route('/group/<group_id>/create-poll', methods=['GET', 'POST'])
def create_poll(group_id):
    if request.method == 'POST':
        title = request.form['poll-title']
        question = request.form['poll-question']
        option = request.form.getlist('poll-option')
        option = ','.join(option)

        # ['option 1', 'option 2']

        # store options into tb_poll_options
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # insert poll into tb_poll
        cursor.execute("INSERT INTO tb_poll (poll_title, poll_body, created_by, group_id)"
                       " VALUES (%s, %s, %s, %s)", (title, question, session['user_id'], group_id))

        # grab newly created poll_id
        cursor.execute("SELECT LAST_INSERT_ID()")
        new_poll_id = cursor.fetchone()
        new_poll_id = new_poll_id['LAST_INSERT_ID()']

        # insert poll options into tb_poll_options
        cursor.callproc('insert_poll_options', [option, new_poll_id])
        mysql.connection.commit()

        return redirect(url_for('into_group', group_id=group_id))


@app.route('/group/<group_id>/poll-vote', methods=['POST'])
def poll_vote(group_id):
    if request.method == 'POST':
        if 'submit-vote' in request.form:
            selected_vote = request.form['poll-option']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

            # get poll_id and option_id from poll_option
            cursor.execute('SELECT poll_id, option_id from tb_poll_options WHERE optionText = %s', (selected_vote,))
            poll_option_details = cursor.fetchall()
            cursor.execute("INSERT INTO tb_poll_responses (poll_id, option_id, user_id)"
                           " VALUES (%s, %s, %s)", (poll_option_details[0]['poll_id'],
                                                    poll_option_details[0]['option_id'], session['user_id']))
            mysql.connection.commit()
            return redirect(url_for('into_group', group_id=group_id))


# ===========================================NEW CHANGES===========================================================
@app.route('/group/<group_name>/create-group-vote', methods=['GET', 'POST'])
def create_groupvote(group_name):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if request.method == 'POST':
        cursor.execute('SELECT group_id from tb_group where group_name = %s', (group_name,))
        group_id = cursor.fetchone()
        group_id = group_id['group_id']

        groupvote_title = request.form['groupvote-title']
        groupvote_type = request.form['voteType']

        print('-----------GROUP VOTE FORM SUBMISSION-----------')
        print(groupvote_title, groupvote_type)

        if groupvote_type == 'close_group':
            # check if close_group groupvote already exists in tb_group_votes
            cursor.execute('SELECT * FROM tb_group_votes WHERE vote_subject = %s AND group_id = %s',
                           (groupvote_type, group_id,))
            close_group_vote_exists = cursor.fetchone()
            if close_group_vote_exists:
                msg = 'You may not create more than one Close Group Vote!'
                return redirect(url_for('into_group', group_id=group_id))
            else:
                # insert group group-vote
                cursor.execute('INSERT INTO tb_group_votes (group_id, vote_subject, user_id) VALUES (%s, %s, %s)',
                               (group_id, groupvote_type, session['user_id']), )

        user_subject = ''
        if groupvote_type == 'praise' or groupvote_type == 'warning' or groupvote_type == 'user_removal':
            user_subject = request.form['user-subject']

            # #check if user_subject exist in group
            cursor.execute('SELECT user_id from tb_group_members where user_name = %s and group_id= %s',
                           (user_subject, group_id,))
            check_user_exists = cursor.fetchone()
            print(check_user_exists)

            if not check_user_exists:
                msg = 'This user does not exist within the group!'
                return redirect(url_for('into_group', group_id=group_id))
            else:
                # insert user group-vote
                cursor.execute(
                    'INSERT INTO tb_group_votes (group_id, vote_subject, user_subject, user_id) VALUES (%s, %s, %s, %s)',
                    (group_id, groupvote_type, check_user_exists['user_id'], session['user_id'],))

        mysql.connection.commit();

    return redirect(url_for('into_group', group_id=group_id))


@app.route('/group/<group_id>/<group_vote_id>/group-vote-response', methods=['GET', 'POST'])
def groupvote_response(group_id, group_vote_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        if 'submit-groupvote' in request.form:
            groupvote_response = request.form['groupvote-option']
            print('-----GROUP VOTE RESPONSE-----')
            print(groupvote_response)

            # insert response to tb_group_vote_responses
            cursor.execute(
                'INSERT INTO tb_group_vote_responses (group_vote_id, group_id, voter_id, vote_response) VALUES (%s, %s, %s, %s)',
                (group_vote_id, group_id, session['user_id'], groupvote_response))

            mysql.connection.commit();

    return redirect(url_for('into_group', group_id=group_id))


@app.route('/group/<group_id>/close', methods=['GET', 'POST'])
def close_group(group_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # get list of user_id in group (given group_name)
    cursor.execute(''
                   'select tb_user.user_id, tb_user.user_name from tb_user '
                   'join tb_group_members on tb_user.user_id = tb_group_members.user_id '
                   'join tb_group on tb_group_members.group_id = tb_group.group_id '
                   'where tb_group.group_id =%s and tb_user.user_id != %s',
                   (group_id, session['user_id']))
    group_members = cursor.fetchall()
    print(group_members)

    if request.method == 'POST':
        # close_group_data = request.json
        open_reason = request.json['openReason']
        close_reason = request.json['closeReason']
        userRatings = request.json['userRatings']
        wb_bb_response = request.json['wbBBOptions']
        print('White/Black list options: ', wb_bb_response)

        print(request.json)
        result = {'url': url_for('home')}

        # iterate through user each user in group - paired with userRating's index
        # insert i = 0, user_id : userRatings in tb_user_evaluation table
        print('--------------EVALUATED GROUP MEMBERS-----------')
        print(group_members)

        for i in range(0, len(group_members)):
            print(group_members[i]['user_name'], userRatings[str(i)])


            cursor.execute(
                'INSERT INTO tb_user_evaluations (group_id, rater_id, evaluation_score, user_id) VALUES (%s, %s, %s, %s)',
                (group_id, session['user_id'], userRatings[str(i)], group_members[i]['user_id']))

            # insert project evaluation into tb_project_evaluations
            cursor.execute(
                'INSERT INTO tb_project_evaluations (project_open_reason, project_close_reason, group_id, user_id) VALUES (%s, %s, %s, %s)',
                (open_reason, close_reason, group_id, group_members[i]['user_id']))

            if wb_bb_response[i] == 'Whitelist':
                print(group_members[i]['user_name'], 'into Logged Users Whitelist')
                # check if user already has in group_member whitelist
                cursor.execute('SELECT user_name_friend FROM tb_whitelist WHERE user_name_friend = %s AND user_id = %s', (group_members[i]['user_name'], session['user_id'],))
                already_whitelisted = cursor.fetchone()
                if not already_whitelisted:
                    cursor.execute('INSERT INTO tb_whitelist (user_id, user_name_friend) VALUES (%s, %s)', (session['user_id'], group_members[i]['user_name'],))
                else:
                    print('This USER IS ALREADY WHITELISTED!!!')

            if wb_bb_response[i] == 'Blacklist':
                print(group_members[i]['user_name'], 'into Logged Users Blacklist')
                # check if group member is in user's whitelist
                cursor.execute('SELECT * from tb_whitelist WHERE user_name_friend = %s AND user_id = %s', (group_members[i]['user_name'], session['user_id'],))
                in_whitelist = cursor.fetchone()
                if in_whitelist:
                    print('This user is in whitelist, removing and putting to blacklist')
                    cursor.execute('DELETE FROM tb_whitelist WHERE user_name_friend = %s AND user_id = %s', (group_members[i]['user_name'], session['user_id'],))

                    cursor.execute('INSERT INTO tb_user_blacklist (user_id, user_name_blocked) VALUES (%s, %s)', (session['user_id'], group_members[i]['user_name'],))
                else:
                    cursor.execute('INSERT INTO tb_user_blacklist (user_id, user_name_blocked) VALUES (%s, %s)',
                                   (session['user_id'], group_members[i]['user_name'],))



            mysql.connection.commit();

        return jsonify(result)

    return render_template('close_group.html', group_id=group_id, group_members=group_members)


@app.route('/message', methods=['GET', 'POST'])
def messageSU():
    if request.method == 'POST':
        message_name = request.form['name']
        message_content = request.form['content']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("INSERT INTO tb_message_su (message_name, message_content)"
                       " VALUES (%s, %s)", (message_name, message_content))
        mysql.connection.commit()
        return render_template('message.html', msg="SENT")
    return render_template('message.html')


@app.route("/adminMessages/", methods=['GET', 'POST'])
@admin_login_required
def adminMessages():
    if request.method == 'POST':
        if "Deletemessage" in request.form:
            message_id = request.form['message_id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('DELETE FROM tb_message_su WHERE message_id = %s', (message_id))
            mysql.connection.commit()
        elif "Deletecompliment" in request.form:
            compliment = request.form['compliment_id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('DELETE FROM tb_compliments WHERE compliment_id = %s', (compliment))
            mysql.connection.commit()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM tb_message_su')
    # Fetch all post records and return result
    messages = cursor.fetchall()
    cursor.execute('SELECT * FROM tb_compliments')
    compliments = cursor.fetchall()
    if messages or compliments:
        return render_template('adminMessages.html', messages=messages, compliments=compliments)
    return render_template('adminMessages.html')


@app.route("/allUsers/", methods=['GET', 'POST'])
@admin_login_required
def adminEdit():
    if request.method == "POST":
        if "Submit" in request.form:
            user_id = request.form['user_id']
            user_scores = int(request.form['user_scores'])
            score = int(request.form['score'])
            insert = user_scores + score
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('UPDATE tb_profile SET user_scores = %s WHERE user_id = %s',
                           (insert, user_id))
            mysql.connection.commit()
        elif 'Blacklist' in request.form:
            user_id = request.form['user_id']
            email = request.form['email']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM tb_blacklist WHERE email =%s",(email,))
            exist = cursor.fetchone()
            if not exist:
                cursor.execute('UPDATE tb_profile SET user_status = %s WHERE user_id = %s',
                               ('0', user_id))
                cursor.execute("INSERT INTO tb_blacklist (email)" "VALUES (%s)", (email,))
                mysql.connection.commit()
                msg = Message("We are sorry to see you go!", recipients=[email])
                msg.body = "Due to your behaviour, you have been blacklisted. You have one login left for you process before you are locked out from Whiteboard forever."
                mail.send(msg)
        elif 'ShutDownGroup' in request.form:
            group_id = request.form['group_id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('INSERT INTO tb_chat (user_id, group_id, chat_content) VALUES (%s, %s, %s)',
                           ([session['user_id']], group_id,
                            "The Super Users have decided to shut down this group - you have a day for processing, then we ask you to initiate a shutdown."))
            mysql.connection.commit()
        # need to take care of group closings

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # find all ordinary users who scores > 25
    cursor.execute('SELECT * FROM tb_profile WHERE user_type = "Ordinary" AND user_scores > 25')
    ou_vip = cursor.fetchall()
    for i in range(len(ou_vip)):
        # update to be VIP
        cursor.execute('UPDATE tb_profile SET user_type = %s WHERE user_id = %s', ('VIP', ou_vip[i]['user_id']))
        mysql.connection.commit()
    # find all VIP who scores < 25
    cursor.execute('SELECT * FROM tb_profile WHERE user_type = "VIP" AND user_scores < 25')
    vip_ou = cursor.fetchall()
    for i in range(len(vip_ou)):
        # demote to be Ordinary user
        cursor.execute('UPDATE tb_profile SET user_type = %s WHERE user_id = %s', ('Ordinary', vip_ou[i]['user_id']))
        mysql.connection.commit()
    #kickout that has a negative repuation number 
    cursor.execute('SELECT * FROM tb_profile WHERE user_status = 1 and user_scores < 0')
    kick_out = cursor.fetchall()
    for i in range(len(kick_out)):
        cursor.execute('UPDATE tb_profile SET user_status = %s WHERE user_id = %s',
                            ('0', kick_out[i]['user_id'])) 
        #add to blacklist 
        cursor.execute('SELECT email FROM tb_user WHERE user_id = %s',((kick_out[i]['user_id']),))
        email = cursor.fetchone()
        cursor.execute("INSERT INTO tb_blacklist (email, lastlogin)" "VALUES (%s,%s)", (email['email'],'0'))
        mysql.connection.commit()

    cursor.execute('SELECT tb_profile.*, tb_user.user_name, tb_user.email'
                   ' FROM tb_user INNER JOIN tb_profile ON tb_profile.user_id = tb_user.user_id')
    all_accounts = cursor.fetchall()
    cursor.execute("SELECT * FROM tb_group")
    all_groups = cursor.fetchall()
    return render_template("allUsers.html", all_accounts=all_accounts, all_groups=all_groups)


if __name__ == '__main__':
    app.run(debug=True)
