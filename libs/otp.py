import random

class OTP:

    def generate(length) :
        OTP = ""
        for i in range(length) :
                        OTP=OTP+str(random.choice(range(0,9)))
        return OTP