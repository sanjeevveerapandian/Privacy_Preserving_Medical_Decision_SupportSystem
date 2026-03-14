import base64
token = "0FBQUFBQnBxdkU0LUtDS1UxY3g4SjltaDRTVFpxUURfOW9OVXlGRGRYUTE3eDV0U0lhR3FBaTU1cW43S3dmQkwzVlN3M2N2U0llV1hLZjNLZ2Z5blZhX0xtQkRsdDFHcHdFZDBXeXVnZzBUb2t5NkEtb0pib3R2V2xsMnpfTTk0dDV6WjI0d2YzMDZZVms3VkpsYzFGSEZ4blAzN0tuVmFEbzR1T054N0prLUZ6b0YtV1I0X0ZVMVdXak5WcFZMQ3EtbEtDbFkyT3B1c0d6X3FJRklCdFFpNlhKQTF6WVZOQT09"
print("Length:", len(token))
try:
    decoded = base64.b64decode(token + "=" * (4 - len(token) % 4))
    print("Decoded snippet:", decoded[:20])
except Exception as e:
    print("Error:", e)
