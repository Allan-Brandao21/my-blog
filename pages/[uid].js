import Prismic from '@prismicio/client'
import {RichText} from 'prismic-reactjs'
import styles from '../styles/post.module.css'
import Head from 'next/head'
const Post = ({data}) =>{
    console.log(data)
    return(
        <div>
        <Head>
        <title>Allan Brandão</title>
        <meta name="description" content="Blog de Allan Brandão" />
        <link rel="icon" href="/favicon.svg" />
      </Head>
        <div className={styles.post} key={data.uid}>
            <h1>{data.data.title[0].text}</h1>
            <span></span> 
            {RichText.render(data.data.content)}
        </div>

        </div>
    )
}

export async function getStaticProps({ params }){
    const apiEndpoint = 'https://allan-blog.cdn.prismic.io/api/v2'
    const Client = Prismic.client(apiEndpoint, {})

    const post = await Client.getByUID('blog_post', params.uid, {
        lang: 'pt-br',
      });

    
      return{
          props:{
              data:post
          }
      }
}

export async function getStaticPaths() {
    const apiEndpoint = 'https://allan-blog.cdn.prismic.io/api/v2'
    const Client = Prismic.client(apiEndpoint, {})
  
    const data = await Client.query(
      Prismic.Predicates.at('document.type', 'blog_post'),
      { orderings: '[my.post.date desc]' }
    )

    const allBlogPosts = []

    data.results.map((post) => {
        allBlogPosts.push({ params: {uid: post.uid}})
    })

    return {
      paths: allBlogPosts,
      fallback: false
    };
  }


export default Post