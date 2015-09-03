from ldap3 import Server, Connection, AUTH_SIMPLE, STRATEGY_SYNC, ALL_ATTRIBUTES, SUBTREE
from ldap3.core.exceptions import LDAPInvalidCredentialsResult


import logging

from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend
from django.conf import settings

logger = logging.getLogger(__name__)

LDAP_INFORMATION = settings.AUTH_INFORMATION['LDAP']

class LDAPBackend(ModelBackend):
    """
    requires ldap3
    https://pypi.python.org/pypi/ldap3
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ldap_server = Server(LDAP_INFORMATION['HOST'], port=LDAP_INFORMATION['PORT'])


    def authenticate(self, username=None, password=None):
        """Authenticate using LDAP"""
        # get user DN
        c = Connection(self.ldap_server,
                       authentication=AUTH_SIMPLE,
                       client_strategy=STRATEGY_SYNC,
                       raise_exceptions=True)
        c.open()
        username_search_filter =  "(uid={})".format(username)
        # check if user is in directory
        if c.search(search_base=LDAP_INFORMATION["BASE_DN"], search_filter=username_search_filter, search_scope=SUBTREE, attributes=ALL_ATTRIBUTES):
            user_information = c.response[0]
            user_dn = user_information["dn"]
            is_valid = False
            c = Connection(self.ldap_server,
                           authentication=AUTH_SIMPLE,
                           user=user_dn,
                           password=password,
                           client_strategy=STRATEGY_SYNC,
                           raise_exceptions=True)
            c.open()
            # attempt to authenticate the user with the directory
            try:
                c.bind()
                is_valid = True
            except LDAPInvalidCredentialsResult as e:
                # check response
                # --> ldap3.__version__ == '0.9.7.4' seems to throw and exception even when the bind is successful...
                #     check the response's 'description'
                if hasattr(e, "response") and len(e.response) >= 1:
                    response_dict = e.response[0]
                    if "description" in response_dict:
                        if response_dict["description"] == "success":
                            is_valid = True
                    else:
                        logger.warn("LDAPInvalidCredentialsResult raised on ({}) login attempt, no 'description' in response.".format(username))
                else:
                    logger.warn("LDAPInvalidCredentialsResult raised on ({}) login attempt, no 'response' attached to exception.".format(username))

            if is_valid:
                now = timezone.now()
                exact_username = user_information['attributes']["uid"][0]
                first_name = " ".join(user_information['attributes']["givenName"])
                last_name = " ".join(user_information["attributes"]["sn"])
                email = user_information['attributes']['mail'][0]
                try:
                    user = User.objects.get(username__exact=exact_username)
                    # always update user profile to synchronize ldap server
                    user.set_password(password)
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    user.last_login = now
                    user.save()
                    logger.info("({}) logged in.".format(username))
                except User.DoesNotExist:
                    # create new user object for internal system usage
                    user = User()
                    user.username = exact_username
                    user.set_password(password)
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    user.is_staff = True
                    user.is_superuser = True
                    user.is_active = True
                    user.last_login = now
                    user.save()
                    logger.info("({}) logged in - initial".format(username))
                return user
        else:
            # search failed!
            logger.error('LDAP Connection.search() failed for: {}'.format(username_search_filter))
        return None

